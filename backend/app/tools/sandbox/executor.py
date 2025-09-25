# app/tools/sandbox/executor.py
"""
Code Sandbox — stateful, Jupyter‑style executor with CEL integration.

Goals (maps to user's requirements):
1) Stateful cell execution so code in later cells can reuse earlier variables.
2) On‑the‑fly package installation ("import and download any module needed").
3) Full read/write access under a provided tmp directory.
4) Summarize code and outputs, and append a structured Step Block to CEL.md.
5) Use an LLM to evaluate outputs vs the task and update the Evaluation line.
6) Optionally use an LLM to write the code for the cell before execution.

Design notes
- Each run/session gets its own Kernel (namespace dict + working dir + CEL path).
- Package install uses pip as a subprocess into the current env (demo‑friendly).
- Outputs are captured (stdout/stderr) and a lightweight artifact index is built
  by hashing files under tmp/. We keep paths relative to the run_dir.
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

from app.core.logging import get_logger
from app.utils.sanitization.code_extracters import _extract_python

logger = get_logger(__name__)

# --------------------------- Public Interfaces --------------------------------

class LLMClient:
    """Minimal LLM interface. Implement .generate(prompt) to return text."""
    def generate(self, prompt: str) -> str:  # pragma: no cover (interface)
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
    code: Optional[Dict[str, Any]]  # {"filename": str, "code": str} or None if error
    stdout: str
    stderr: str
    display: Optional[Any]
    files_out: List[Dict[str, Any]]
    summary: str  # short textual summary used for CEL

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
    """High-level facade managing kernels by run_id and CEL.md updates."""

    def __init__(self, base_tmp_dir: str = "tmp"):
        self.base_tmp = pathlib.Path(base_tmp_dir).resolve()
        self.base_tmp.mkdir(parents=True, exist_ok=True)
        self._kernels: Dict[str, Kernel] = {}

    # ---------- Kernel/session management ----------
    def _run_dir(self, run_id: str) -> pathlib.Path:
        return self.base_tmp / run_id

    def get_kernel(self, run_id: str) -> Kernel:
        if run_id not in self._kernels:
            self._kernels[run_id] = Kernel(self._run_dir(run_id))
        return self._kernels[run_id]

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

    # ---------- CEL utilities ----------
    def cel_path(self, run_id: str) -> pathlib.Path:
        return self._run_dir(run_id) / "CEL.md"

    def _artifact_index(self, run_dir: pathlib.Path) -> List[Dict[str, Any]]:
        artifacts: List[Dict[str, Any]] = []
        for p in run_dir.rglob("*"):
            if not p.is_file():
                continue
            try:
                data = p.read_bytes()
            except Exception:
                continue
            rel = p.relative_to(run_dir)
            artifacts.append({
                "name": p.name,
                "path": str(rel),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest()[:12],
            })
        return artifacts

    def _append_cel_step(
        self,
        run_id: str,
        tool_name: str,
        inputs_summary: str,
        what_i_did: List[str],
        artifacts: List[Dict[str, Any]],
        evaluation_line: str = "PENDING",
    ) -> None:
        cel = self.cel_path(run_id)
        cel.parent.mkdir(parents=True, exist_ok=True)
        when = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        art_lines = "\n".join(
            f"- {a['name']}: `{a['path']}` (size={a['size']}, sha256={a['sha256']})" for a in artifacts
        )
        block = f"""
## Step: {tool_name}
**When:** {when}
**Inputs:** {inputs_summary}
**What I did:**
""".rstrip("\n") + "\n" + "\n".join(f"- {b}" for b in what_i_did if b) + "\n" + f"""
**Artifacts:**
{art_lines}

**Next steps:**
**Evaluation (by Evaluator):** {evaluation_line}
"""
        header = "# Context Engineering Log (CEL)\n\n"
        prev = cel.read_text() if cel.exists() else header
        cel.write_text(prev + block)

    @staticmethod
    def _extract_json_blob(text: str) -> dict:
        s, e = text.find("{"), text.rfind("}")
        if s == -1 or e == -1 or e <= s:
            raise ValueError("Evaluator did not return JSON.")
        return json.loads(text[s:e+1])

    def _update_last_eval_block(self, run_id: str, verdict: str, eval_text: str, output_summary: str) -> None:
        """Replace last '**Evaluation (by Evaluator):' with a structured block."""
        cel = self.cel_path(run_id)
        text = cel.read_text() if cel.exists() else ""
        if not text:
            return
        parts = text.rsplit("**Evaluation (by Evaluator):**", 1)
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
        cel.write_text(prefix + "**Evaluation (by Evaluator):" + block + remainder)

    # ---------- LLM prompts ----------
    def _build_writer_prompt(self, task: str, context_preview: str) -> str:
        return (
            "You are a senior Python data engineer. Write ONE Python cell to accomplish the task.\n"
            "Environment:\n- CWD is the run directory (use relative paths like 'spend.csv').\n"
            "Hard rules:\n- Output ONLY raw Python code (no markdown fences).\n"
            "- If ETL/EDA is required, do it in this cell.\n"
            "- Save new outputs under the current directory.\n\n"
            f"Task:\n{task}\n\n"
            f"Preview of namespace/files:\n{context_preview}\n"
        )

    def _build_eval_prompt(self, task: str, stdout: str, stderr: str, artifacts: List[Dict[str, Any]]) -> str:
        payload = {
            "task": task,
            "stdout": (stdout or "")[:20000],
            "stderr": (stderr or "")[:8000],
            "files_out": artifacts or [],
            "code_filename": "",  
        }
        return (
            "Given the task, stdout, stderr, and files produced by a Python cell, evaluate how well the task was accomplished and give the code a filename.\n"
            "Inputs JSON below. Return ONE JSON object with keys: eval, verdict, output_summary, code_filename.\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    def _build_repair_prompt(self, task: str, code: str, stdout: str, stderr: str) -> str:
        return (
            "You wrote a Python cell for the task below, but it failed.\n"
            "Fix the code. Output ONLY raw Python code for a single cell (no fences, no commentary).\n\n"
            f"Task:\n{task}\n\n"
            f"Previous code:\n{code}\n\n"
            f"STDOUT (truncated):\n{stdout[:2000]}\n\nSTDERR (truncated):\n{stderr[:2000]}\n"
            "Guidance:\n- Use CWD-relative paths.\n- Prefer simple, explicit code.\n"
            "- If files are missing, create them or handle gracefully.\n"
        )

    def _has_error(self, stderr: str) -> bool:
        return ("Traceback (most recent call last)" in (stderr or "")) or ("[Sandbox] Timeout" in (stderr or ""))

    def _maybe_repair_with_llm(
        self,
        run_id: str,
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
        run_id: str,
        req: ExecRequest,
        code_llm: Optional[LLMClient] = None,
        eval_llm: Optional[LLMClient] = None,
    ) -> ExecResult:
        """Execute a cell with optional LLM writer/evaluator and CEL updates."""
        cel_file = self.cel_path(run_id)
        cel_text = ""
        if cel_file.exists():
            cel_text = cel_file.read_text(encoding="utf-8", errors="ignore")
            if len(cel_text) > 20000:
                cel_text = cel_text[-20000:]

        if req.language.lower() != "python":
            raise ValueError("Only Python is supported at the moment")

        kernel = self.get_kernel(run_id)
        run_dir = self._run_dir(run_id)

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
        writer_note = None  # <-- ensure defined in both paths

        if req.code:
            code_to_run = _extract_python(req.code)
        else:
            if req.use_llm_writer and code_llm and req.task:
                ns_keys = sorted([k for k in list(kernel.globals.keys()) if not k.startswith("__")])
                files = [str(p.relative_to(run_dir)) for p in run_dir.rglob("*") if p.is_file()]
                preview = "Namespace keys: " + ", ".join(ns_keys[:50]) + "\nFiles: " + ", ".join(files[:50])

                prompt = self._build_writer_prompt(req.task, preview)
                cel_prompt = ("CEL.md (context):\n" + cel_text + "\n\n" + prompt)

                cel_file = self.cel_path(run_id)
                code_to_run = code_llm.generate(
                    cel_prompt,
                    files=[str(cel_file)] if cel_file.exists() else None,
                )
                writer_note = "code generated by LLM (context: CEL.md)"

        # (1) Execute
        stdout, stderr, display = kernel.exec_code(code_to_run, timeout_s=req.timeout_s)
        if pip_log:
            stderr = pip_log + "\n" + (stderr or "")

        # (2b) Auto-repair
        attempts_used = 0
        code_to_run, stdout, stderr, display, attempts_used = self._maybe_repair_with_llm(
            run_id=run_id,
            req=req,
            kernel=kernel,
            code_llm=code_llm,
            code=code_to_run,
            stdout=stdout,
            stderr=stderr,
            display=display,
        )

        # (3) Artifact scan
        artifacts = self._artifact_index(run_dir)

        # (4) Summarize for CEL
        summary = self._summarize_for_cel(code_to_run, stdout, stderr)
        self._append_cel_step(
            run_id=run_id,
            tool_name="sandbox.exec",
            inputs_summary=self._inputs_summary(req, writer_note),
            what_i_did=[
                "Executed Python cell in persistent kernel",
                "Installed packages: " + (", ".join(req.pip) if req.pip else "none"),
                attempts_used and f"Repaired code with LLM {attempts_used} time(s)",
                "Captured stdout/stderr and scanned artifacts",
            ],
            artifacts=artifacts,
            evaluation_line="PENDING",
        )

        logger.info(f"exec_cell: run_id={run_id}, final code:\n{code_to_run}\n--- end code ---\n\n")

        # (5) LLM evaluation (optional)
        verdict = None
        eval_text = ""
        output_summary = ""
        code_filename = ""

        if eval_llm and req.task:
            cel_file = self.cel_path(run_id)
            cel_text = cel_file.read_text(encoding="utf-8", errors="ignore") if cel_file.exists() else ""
            eval_prompt = ("CEL.md (context):\n" + cel_text[-20000:] + "\n\n" +
                           self._build_eval_prompt(req.task, stdout, stderr, artifacts))
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
                code_filename = f"cell.py"

            self._update_last_eval_block(run_id, verdict, eval_text, output_summary)

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

        return ExecResult(
            ok=ok,
            code=code_obj,
            stdout=stdout,
            stderr=stderr,
            display=display,
            files_out=artifacts,
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

    def _summarize_for_cel(self, code: str, stdout: str, stderr: str) -> str:
        code_snip = code.strip()
        code_snip = (code_snip[:400] + "…") if len(code_snip) > 400 else code_snip
        out_snip = (stdout[:400] + "…") if len(stdout) > 400 else stdout
        err_snip = (stderr[:200] + "…") if len(stderr) > 200 else stderr
        parts = ["Code:\n" + code_snip]
        if out_snip:
            parts.append("STDOUT:\n" + out_snip)
        if err_snip:
            parts.append("STDERR:\n" + err_snip)
        return "\n\n".join(parts)