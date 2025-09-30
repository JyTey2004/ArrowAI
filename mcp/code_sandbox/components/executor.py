# Code Sandbox — stateful, Jupyter-style executor with Run Log and S3 sync.
"""
Code Sandbox — stateful, Jupyter-style executor with Run Log and S3 sync.

Goals (maps to user's requirements):
1) Stateful cell execution so code in later cells can reuse earlier variables.
2) On-the-fly package installation ("import and download any module needed").
3) Full read/write access under a provided tmp directory.
4) Summarize code and outputs, and append a structured Step Block to RUN_LOG.md.
5) Optionally use an LLM to write the code for the cell before execution.
6) Sync ONLY artifacts produced under the outputs/ directory to S3, and return files_out
   with only: name, path (S3 URI), size.

Design notes
- Each run/session gets its own Kernel (namespace dict + working dir + Run Log path).
- Package install uses pip as a subprocess into the current env (demo-friendly).
- Outputs are captured (stdout/stderr) and a lightweight artifact index is built
  by hashing files under outputs/. We keep paths relative to the run_dir.
- LLMs are abstracted behind a minimal interface (LLMClient). Wire your model
  of choice (e.g., OpenAI, Anthropic) by implementing .generate().

Security: This executes arbitrary Python. For demos only; do not expose publicly
without sandboxing (containers, seccomp, resource limits, network egress blocks).
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import textwrap
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import logging
from utils.code_extracters import _extract_python
from aws.s3_client import S3Client  # NEW

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------- Public Interfaces --------------------------------

class LLMClient:
    """Minimal LLM interface. Implement .generate(prompt) to return text."""
    def generate(self, prompt: str, **kwargs) -> str:  # pragma: no cover (interface)
        raise NotImplementedError

@dataclasses.dataclass
class ExecRequest:
    code: Optional[str] = None
    language: str = "python"
    files_in: Optional[List[Dict[str, str]]] = None
    timeout_s: Optional[int] = None
    task: Optional[str] = None
    pip: Optional[List[str]] = None
    use_llm_writer: bool = False
    repair_attempts: int = 2

@dataclasses.dataclass
class ExecResult:
    ok: bool
    code: Optional[Dict[str, Any]]  # {"filename": str, "text": str} or None text if error
    stdout: str
    stderr: str
    display: Optional[Any]
    files_out: List[Dict[str, Any]]  # [{name, path (S3 or local), size}]
    summary: str  # short textual summary used for Run Log

# ----------------------------- Kernel -----------------------------------------

class Kernel:
    """One stateful Python execution context per run/session."""
    def __init__(self, run_dir: pathlib.Path):
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.globals: Dict[str, Any] = {
            "__name__": "__sandbox__",
            "__file__": str(self.run_dir / "__cell__.py"),
            "RUN_DIR": self.run_dir,
        }
        self.locals: Dict[str, Any] = self.globals

    def exec_code(self, code: str, timeout_s: Optional[int] = None) -> Tuple[str, str, Optional[Any]]:
        """Execute *Python* code in this kernel, capturing stdout/stderr."""
        normalized = textwrap.dedent(code)
        last_value: Optional[Any] = None
        try:
            compiled = compile(normalized, str(self.run_dir / "__cell__.py"), "exec")
        except SyntaxError:
            try:
                compiled = compile(normalized, str(self.run_dir / "__cell__.py"), "single")
            except Exception:
                compiled = None

        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()

        def _run():
            nonlocal last_value
            old_cwd = os.getcwd()
            try:
                os.makedirs(self.run_dir, exist_ok=True)
                os.chdir(self.run_dir)
                if compiled:
                    exec(compiled, self.globals, self.locals)
                else:
                    exec(normalized, self.globals, self.locals)
                last_value = self.globals.get("_", None)
            except Exception:
                import traceback
                traceback.print_exc(file=stderr_buf)
            finally:
                try:
                    os.chdir(old_cwd)
                except Exception:
                    pass

        thread = threading.Thread(target=lambda: self._redirected(_run, stdout_buf, stderr_buf), daemon=True)
        thread.start()
        thread.join(timeout=timeout_s)
        if thread.is_alive():
            stderr_buf.write(f"\n[Sandbox] Timeout after {timeout_s}s — cell did not complete.\n")
        return stdout_buf.getvalue(), stderr_buf.getvalue(), last_value

    @staticmethod
    def _redirected(fn, out: io.StringIO, err: io.StringIO):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            fn()

# --------------------------- Sandbox (Facade) ---------------------------------

class CodeSandbox:
    """High-level facade managing kernels by thread_id, Run Log updates, and S3 sync."""

    def __init__(
        self,
        base_tmp_dir: str = "tmp",
        s3_client: Optional[S3Client] = None,
        s3_prefix: str = "threads",  # s3://bucket/threads/<thread_id>/artifacts/...
        outputs_dirname: str = "outputs",
        inputs_dirname: str = "inputs",
    ):
        self.base_tmp = pathlib.Path(base_tmp_dir).resolve()
        self.base_tmp.mkdir(parents=True, exist_ok=True)
        self._kernels: Dict[str, Kernel] = {}

        # S3 config
        self.s3: Optional[S3Client] = s3_client
        self.s3_prefix = s3_prefix.strip("/ ")

        # Layout
        self.outputs_dirname = outputs_dirname.strip("/ ")
        self.inputs_dirname = inputs_dirname.strip("/ ")

    # ---------- Kernel/session management ----------
    def _run_dir(self, thread_id: str) -> pathlib.Path:
        return self.base_tmp / thread_id

    def _ensure_layout(self, thread_id: str) -> None:
        """Ensure run_dir, outputs/, and inputs/ exist."""
        rd = self._run_dir(thread_id)
        (rd / self.outputs_dirname).mkdir(parents=True, exist_ok=True)
        (rd / self.inputs_dirname).mkdir(parents=True, exist_ok=True)

    def get_kernel(self, thread_id: str) -> Kernel:
        if thread_id not in self._kernels:
            self._ensure_layout(thread_id)
            kernel = Kernel(self._run_dir(thread_id))
            # inject convenience globals
            kernel.globals["OUTPUTS_DIR"] = str(self._run_dir(thread_id) / self.outputs_dirname)
            kernel.globals["INPUTS_DIR"] = str(self._run_dir(thread_id) / self.inputs_dirname)
            self._kernels[thread_id] = kernel
        else:
            # Make sure layout still exists (idempotent)
            self._ensure_layout(thread_id)
            k = self._kernels[thread_id]
            k.globals["OUTPUTS_DIR"] = str(self._run_dir(thread_id) / self.outputs_dirname)
            k.globals["INPUTS_DIR"] = str(self._run_dir(thread_id) / self.inputs_dirname)
        return self._kernels[thread_id]

    # ---------- Package management ----------
    def ensure_packages(self, packages: Iterable[str]) -> Tuple[bool, str]:
        """Install packages via pip into the current environment."""
        if not packages:
            return True, ""
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *packages]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            ok = proc.returncode == 0
            log = (proc.stdout or "") + (proc.stderr or "")
            return ok, log
        except Exception as e:  # pragma: no cover
            return False, f"pip failed: {e}"

    # ---------- Run Log utilities ----------
    def run_log_path(self, thread_id: str) -> pathlib.Path:
        return self._run_dir(thread_id) / "RUN_LOG.md"

    def _append_run_step(
        self,
        thread_id: str,
        tool_name: str,
        inputs_summary: str,
        what_i_did: List[str],
        artifacts: List[Dict[str, Any]],
        evaluation_line: str = "PENDING",
    ) -> None:
        logf = self.run_log_path(thread_id)
        logf.parent.mkdir(parents=True, exist_ok=True)
        when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        art_lines = "\n".join(
            f"- {a['name']}: `{a['path']}` (size={a['size']})" for a in artifacts
        )
        block = (
            f"\n## Step: {tool_name}\n"
            f"**When:** {when}\n"
            f"**Inputs:** {inputs_summary}\n"
            f"**What I did:**\n"
            + "\n".join(f"- {b}" for b in what_i_did if b)
            + "\n**Artifacts (outputs/ only):**\n"
            + (art_lines or "- (none)")
            + f"\n\n**Next steps:**\n"
            f"**Evaluation:** {evaluation_line}\n"
        )
        header = "# Run Log\n\n"
        prev = logf.read_text(encoding="utf-8", errors="ignore") if logf.exists() else header
        logf.write_text(prev + block, encoding="utf-8")
        
    def _update_last_eval_block(self, thread_id: str, verdict: str, eval_text: str, output_summary: str) -> None:
        """Replace last '**Evaluation (by Evaluator):' with a structured block."""
        run_log = self.run_log_path(thread_id)
        text = run_log.read_text() if run_log.exists() else ""
        if not text:
            return
        parts = text.rsplit("**Evaluation:**", 1)
        if len(parts) != 2:
            return
        prefix, tail = parts
        tail_split = tail.split("\n", 1)
        remainder = tail_split[1] if len(tail_split) == 2 else ""
        block = (
            f" {verdict}\n"
            f"**Eval:** {eval_text}\n"
            f"**Output summary:** {output_summary}\n"
        )
        run_log.write_text(prefix + "**Evaluation (by Evaluator):**" + block + remainder)

    # ---------- Artifact indexing ----------
    def _artifact_index(self, run_dir: pathlib.Path, only_under: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Scan files for artifacts. If only_under is set, scan only that subdirectory.
        Returns list of dicts: {name, path (relative to run_dir), size, sha256}
        """
        artifacts: List[Dict[str, Any]] = []
        base = run_dir / only_under if only_under else run_dir
        if not base.exists():
            return artifacts

        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                data = p.read_bytes()
            except Exception:
                continue
            rel = p.relative_to(run_dir)
            artifacts.append({
                "name": p.name,
                "path": str(rel).replace("\\", "/"),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()[:12],
            })
        return artifacts

    # ---------- S3 sync ----------
    def _s3_key_for(self, thread_id: str, relpath: str) -> str:
        norm = relpath.replace("\\", "/").lstrip("./")
        return f"{self.s3_prefix}/{thread_id}/artifacts/{norm}"

    def _sync_artifacts_to_s3(
        self, thread_id: str, artifacts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Upload each artifact (outputs/ only) to S3.
        Returns a new list with ONLY: { name, path: S3 URI (or local if no S3), size }.
        """
        run_dir = self._run_dir(thread_id)
        out: List[Dict[str, Any]] = []

        prefix = f"{self.outputs_dirname}/".replace("\\", "/")

        for a in artifacts:
            # absolute safety: never sync anything outside outputs/
            if not a["path"].replace("\\", "/").startswith(prefix):
                logger.info(f"Skipping non-outputs artifact: {a['path']}")
                continue

            local = (run_dir / a["path"]).resolve()
            if not local.is_file():
                out.append({"name": a["name"], "path": a["path"], "size": a["size"]})
                continue

            if not self.s3:
                # No S3 → return local relative path
                out.append({"name": a["name"], "path": a["path"], "size": a["size"]})
                continue

            key = self._s3_key_for(thread_id, a["path"])
            try:
                self.s3.put_file(
                    local_path=str(local),
                    key=key,
                    content_type=None,     # auto-guess via client
                    metadata={"thread_id": thread_id, "filename": a.get("name", "")},
                    compute_sha256=False,
                )
                out.append({
                    "name": a["name"],
                    "uri": f"s3://{self.s3.bucket}/{key}",
                    "size": a["size"],
                })
            except Exception as e:
                logger.warning(f"S3 upload failed for {local}: {e}")
                out.append({"name": a["name"], "path": a["path"], "size": a["size"]})

        return out

    # ---------- LLM prompts ----------
    def _build_writer_prompt(self, task: str, context_preview: str, run_log: str) -> str:
        return (
            "Write ONE Python cell to accomplish the task.\n"
            "Environment captures ONLY STDOUT — nothing is visible unless printed.\n"
            "Environment:\n"
            "- CWD is the run directory; you can read files by filename if present.\n"
            "- A directory named 'outputs' already exists. SAVE **all** files you create under 'outputs/'.\n"
            "- Convenience variables are provided: OUTPUTS_DIR and INPUTS_DIR (strings with absolute paths).\n"
            "\n"
            "HARD RULES:\n"
            "- Output ONLY raw Python code (no markdown fences).\n"
            "- NEVER use `return` at top level; do not rely on variable echo. Use print(...) for everything.\n"
            "- Prefix required diagnostics with 'EVIDENCE:' so they can be parsed.\n"
            "- After writing each artifact, print: 'ARTIFACT: outputs/<filename>' (relative path under the outputs/ dir).\n"
            "- Do NOT write files anywhere except under outputs/.\n"
            "- If a required column or input is missing/unknown, print 'ERROR: <message>' and stop (do not fabricate).\n"
            "- Always end with: print('DONE')\n"
            "- If ETL/EDA is required, do it in this cell. Save new outputs under the outputs/ directory.\n"
            "- Do not validate remote paths or create fake data.\n"
            "\n"
            "DO (examples to imitate):\n"
            "print('EVIDENCE: key=row_count value=', len(df))\n"
            "print('EVIDENCE: key=date_min value=', str(df[date_col].min()))\n"
            "print('EVIDENCE: key=unique_year_month value=', ym.to_json(orient=\"records\"))\n"
            "df.to_csv('outputs/profile.csv', index=False)\n"
            "print('ARTIFACT: outputs/profile.csv')\n"
            "with open('outputs/profile_summary.md', 'w', encoding='utf-8') as f:\n"
            "    f.write('# Profile Summary\\n...')\n"
            "print('ARTIFACT: outputs/profile_summary.md')\n"
            "print('DONE')\n"
            "\n"
            "DON'T:\n"
            "# return results  # FORBIDDEN\n"
            "# df.head()       # Invisible without print\n"
            "# display(df)     # Invisible here\n"
            "\n"
            f"Task:\n{task}\n\n"
            f"Run Log (most recent 2000 chars):\n{run_log[-2000:]}\n\n"
            f"Preview of namespace/files:\n{context_preview}\n"
        )

    def _build_eval_prompt(self, task: str, stdout: str, stderr: str, code: str, artifacts: List[Dict[str, Any]]) -> str:
        payload = {
            "task": task,
            "code": code,
            "stdout": (stdout or "")[:20000],
            "stderr": (stderr or "")[:8000],
            "files_out": artifacts or [],
            "code_filename": "",
        }
        return (
            "Given the task, stdout, stderr, and files produced by a Python cell, evaluate how well the task was accomplished and give the code a filename.\n"
            "output_summary should be a concise summary of the main outputs including artifacts produced if any in bullet points.\n"
            "Inputs JSON below. Return ONE JSON object with keys: eval, verdict, output_summary, code_filename.\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    def _build_repair_prompt(self, task: str, code: str, stdout: str, stderr: str) -> str:
        return (
            "You wrote a Python cell for the task below, but it failed.\n"
            "Fix the code. Output ONLY raw Python code for a single cell (no fences, no commentary).\n\n"
            "HARD RULES:\n"
            "- Output ONLY raw Python code (no markdown fences).\n"
            "- NEVER use `return` at top level; do not rely on variable echo. Use print(...) for everything.\n"
            "- Prefix required diagnostics with 'EVIDENCE:' so they can be parsed.\n"
            "- After writing each artifact, print: 'ARTIFACT: outputs/<filename>' (relative path under the outputs/ dir).\n"
            "- Do NOT write files anywhere except under outputs/.\n"
            "- If a required column or input is missing/unknown, print 'ERROR: <message>' and stop (do not fabricate).\n"
            "- Always end with: print('DONE')\n"
            "- If ETL/EDA is required, do it in this cell. Save new outputs under the outputs/ directory.\n"
            "- Do not validate remote paths or create fake data.\n"
            "\n"
            "DO (examples to imitate):\n"
            "print('EVIDENCE: key=row_count value=', len(df))\n"
            "print('EVIDENCE: key=date_min value=', str(df[date_col].min()))\n"
            "print('EVIDENCE: key=unique_year_month value=', ym.to_json(orient=\"records\"))\n"
            "df.to_csv('outputs/profile.csv', index=False)\n"
            "print('ARTIFACT: outputs/profile.csv')\n"
            "with open('outputs/profile_summary.md', 'w', encoding='utf-8') as f:\n"
            "    f.write('# Profile Summary\\n...')\n"
            "print('ARTIFACT: outputs/profile_summary.md')\n"
            "print('DONE')\n"
            "\n"
            "DON'T:\n"
            "# return results  # FORBIDDEN\n"
            "# df.head()       # Invisible without print\n"
            "# display(df)     # Invisible here\n"
            f"Task:\n{task}\n\n"
            f"Previous code:\n{code}\n\n"
            f"STDOUT (truncated):\n{stdout[:2000]}\n\nSTDERR (truncated):\n{stderr[:2000]}\n"
            "Guidance:\n- Use CWD-relative paths.\n- Prefer simple, explicit code.\n"
            "- Always save files to 'outputs/'.\n"
        )

    @staticmethod
    def _extract_json_blob(text: str) -> dict:
        s, e = text.find("{"), text.rfind("}")
        if s == -1 or e == -1 or e <= s:
            raise ValueError("Evaluator did not return JSON.")
        return json.loads(text[s:e+1])

    def _has_error(self, stderr: str) -> bool:
        return ("Traceback (most recent call last)" in (stderr or "")) or ("[Sandbox] Timeout" in (stderr or ""))

    def _maybe_repair_with_llm(
        self,
        thread_id: str,
        req: ExecRequest,
        kernel: Kernel,
        code_llm: Optional[LLMClient],
        code: str,
        stdout: str,
        stderr: str,
        display: Optional[Any],
    ) -> Tuple[str, str, str, Optional[Any], int]:
        """Attempt to auto-repair failed code using the LLM up to req.repair_attempts times."""
        attempts_used = 0
        if not code_llm or not req.task or req.repair_attempts <= 0:
            return code, stdout, stderr, display, attempts_used

        while attempts_used < req.repair_attempts and self._has_error(stderr):
            prompt = self._build_repair_prompt(req.task, code, stdout, stderr)
            fixed = code_llm.generate(prompt)
            fixed = _extract_python(fixed)
            code = fixed
            stdout, stderr, display = kernel.exec_code(code, timeout_s=req.timeout_s)
            attempts_used += 1

        return code, stdout, stderr, display, attempts_used

    # ---------- Public API ----------
    def exec_cell(
        self,
        thread_id: str,
        req: ExecRequest,
        code_llm: Optional[LLMClient] = None,
        eval_llm: Optional[LLMClient] = None,
    ) -> ExecResult:
        """Execute a cell with optional LLM writer/evaluator, update Run Log, and sync artifacts to S3 (outputs/ only)."""
        if req.language.lower() != "python":
            raise ValueError("Only Python is supported at the moment")
        
        logger.info(f"exec_cell: thread_id={thread_id}, received task={req.task}, code length={len(req.code) if req.code else 0}, pip={req.pip}, use_llm_writer={req.use_llm_writer}, repair_attempts={req.repair_attempts}")

        kernel = self.get_kernel(thread_id)
        run_dir = self._run_dir(thread_id)
        self._ensure_layout(thread_id)  # idempotent

        # (2) Ensure packages
        pip_log = ""
        if req.pip:
            ok, pip_log = self.ensure_packages(req.pip)
            if not ok:
                pip_log = "[pip install failed]\n" + pip_log

        # (6) LLM code writer (optional)
        if not req.code and not req.use_llm_writer:
            raise ValueError("No code provided and use_llm_writer is False")

        code_to_run = ""
        writer_note = None  # ensure defined in both paths

        if req.code:
            code_to_run = _extract_python(req.code)
        elif req.use_llm_writer and code_llm and req.task:
            ns_keys = sorted([k for k in list(kernel.globals.keys()) if not k.startswith("__")])
            files = [str(p.relative_to(run_dir)).replace("\\", "/") for p in run_dir.rglob("*") if p.is_file()]
            preview = "Namespace keys: " + ", ".join(ns_keys[:50]) + "\nFiles: " + ", ".join(files[:50])
            
            run_log = self.run_log_path(thread_id).read_text(encoding="utf-8", errors="ignore") if self.run_log_path(thread_id).exists() else "New session."

            prompt = self._build_writer_prompt(req.task, preview, run_log)
            code_to_run = _extract_python(code_llm.generate(prompt))
            writer_note = "code generated by LLM"
            
        logger.info(f"exec_cell: thread_id={thread_id}, code to run:\n{code_to_run}\n--- end code ---\n\n")

        # (1) Execute
        stdout, stderr, display = kernel.exec_code(code_to_run, timeout_s=req.timeout_s)
        if pip_log:
            stderr = pip_log + "\n" + (stderr or "")
            
        logger.info(f"exec_cell: thread_id={thread_id}, initial exec stdout:\n{stdout}\n--- end stdout ---\n\n")

        # (2b) Auto-repair
        attempts_used = 0
        code_to_run, stdout, stderr, display, attempts_used = self._maybe_repair_with_llm(
            thread_id=thread_id,
            req=req,
            kernel=kernel,
            code_llm=code_llm,
            code=code_to_run,
            stdout=stdout,
            stderr=stderr,
            display=display,
        )

        # (3) Artifact scan — outputs/ only
        artifacts = self._artifact_index(run_dir, only_under=self.outputs_dirname)

        # (4) Summarize & append Run Log (Run Log is never passed to any LLM)
        summary = self._summarize_for_run_log(code_to_run, stdout, stderr)  # name retained; only used for text
        self._append_run_step(
            thread_id=thread_id,
            tool_name="sandbox.exec",
            inputs_summary=self._inputs_summary(req, writer_note),
            what_i_did=[
                "Executed Python cell in persistent kernel",
                "Installed packages: " + (", ".join(req.pip) if req.pip else "none"),
                attempts_used and f"Repaired code with LLM {attempts_used} time(s)",
                f"Captured stdout/stderr and scanned '{self.outputs_dirname}/' for artifacts",
            ],
            artifacts=artifacts,
            evaluation_line="PENDING",
        )

        # Rescan outputs/ so any run-log-triggered files in outputs (rare) would be included
        artifacts_after = self._artifact_index(run_dir, only_under=self.outputs_dirname)

        logger.info(f"exec_cell: thread_id={thread_id}, final code:\n{code_to_run}\n--- end code ---\n\n")

        # (5) LLM evaluation (optional) — DO NOT pass Run Log content
        verdict = None
        eval_text = ""
        output_summary = ""
        code_filename = ""

        if eval_llm and req.task:
            eval_prompt = self._build_eval_prompt(req.task, stdout, stderr, code_to_run, artifacts_after)
            raw = eval_llm.generate(eval_prompt).strip()
            try:
                obj = self._extract_json_blob(raw)
                verdict = (obj.get("verdict") or "").strip()
                eval_text = (obj.get("eval") or "").strip()
                output_summary = (obj.get("output_summary") or "").strip()
                code_filename = (obj.get("code_filename") or "").strip()
            except Exception as e:
                verdict = f"FAIL — evaluator JSON parse error: {e}"
                eval_text = "Evaluator did not return valid JSON."
                output_summary = (stdout or "")[:800]
                code_filename = "cell.py"
                
        self._update_last_eval_block(
            thread_id=thread_id,
            verdict=verdict or "NO EVALUATION",
            eval_text=eval_text or (stderr or "")[:800],
            output_summary=output_summary or (stdout or "")[:800],
        )
        
        if verdict and isinstance(verdict, str) and verdict.upper().startswith("FAIL"):
            ok = False
        else:
            ok = ("Traceback (most recent call last)" not in stderr) and ("[Sandbox] Timeout" not in stderr)

        final_summary = output_summary or summary

        # If there is error, we do not return the code that was run
        if not ok:
            code_to_run = None

        code_obj = {
            "filename": code_filename or "cell.py",
            "text": code_to_run or "",
        }

        # (6) Sync artifacts (outputs/ only) to S3 and reduce to minimal surface (name, path, size)
        files_out_minimal = self._sync_artifacts_to_s3(thread_id, artifacts_after)

        return ExecResult(
            ok=ok,
            code=code_obj,
            stdout=stdout,
            stderr=stderr,
            display=display,
            files_out=files_out_minimal,   # ONLY name, path (S3 or local), size
            summary=final_summary,
        )

    # ---------- Helpers ----------
    def _inputs_summary(self, req: ExecRequest, writer_note: Optional[str]) -> str:
        fields = {
            "language": req.language,
            "timeout_s": req.timeout_s,
            "task": (req.task[:200] + "…") if req.task else None,
            "writer": writer_note,
        }
        fields = {k: v for k, v in fields.items() if v is not None}
        return json.dumps(fields)

    def _summarize_for_run_log(self, code: str, stdout: str, stderr: str) -> str:
        # Retain the function name for compatibility; used only for local text summary
        code_snip = (code or "").strip()
        code_snip = (code_snip[:400] + "…") if len(code_snip) > 400 else code_snip
        out_snip = (stdout[:400] + "…") if len(stdout) > 400 else stdout
        err_snip = (stderr[:200] + "…") if len(stderr) > 200 else stderr
        parts = ["Code:\n" + code_snip]
        if out_snip:
            parts.append("STDOUT:\n" + out_snip)
        if err_snip:
            parts.append("STDERR:\n" + err_snip)
        return "\n\n".join(parts)
