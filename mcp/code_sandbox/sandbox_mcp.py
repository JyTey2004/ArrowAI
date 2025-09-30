# mcp/sandbox/sandbox_mcp.py
from __future__ import annotations

import base64
import pathlib
import time
import os
import logging, sys
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Context  # SDK's FastMCP, stdio-friendly
from components.executor import CodeSandbox, ExecRequest  # your code
from components.models import CodeExecInput
from services.openai_client import OpenAIClient  # your OpenAI wrapper
from utils.LLMAdapter import LLMAdapter  # your LLMClient adapter

from aws.s3_client import S3Client  # your S3 wrapper
s3c = S3Client(
    bucket_name=os.environ.get("MCP_BUCKET", "arrowai"),
    region_name=os.environ.get("AWS_REGION", "ap-southeast-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)

host = os.getenv("SANDBOX_HOST", "127.0.0.1")
port = int(os.getenv("SANDBOX_PORT", "8787"))
path = os.getenv("SANDBOX_PATH", "/mcp")
mcp = FastMCP("Sandbox", port=port, host=host, mount_path=path)  # or transport="stdio" for stdio
sandbox = CodeSandbox(base_tmp_dir="tmp", s3_client=s3c)  # all I/O stays under tmp/

def _setup_logging():
    level = os.getenv("SANDBOX_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,  # <-- IMPORTANT: log to stderr
    )
    # Optional: quiet noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    # Optional: if FastMCP uses std logging:
    logging.getLogger("mcp").setLevel(logging.INFO)

_setup_logging()
log = logging.getLogger("sandbox")

def _run_dir(thread_id: str) -> pathlib.Path:
    return sandbox._run_dir(thread_id).resolve()

def _inputs_dir(thread_id: str) -> pathlib.Path:
    """Absolute path to run_dir/inputs for this thread."""
    rd = _run_dir(thread_id)
    d = rd / sandbox.inputs_dirname
    d.mkdir(parents=True, exist_ok=True)
    return d

def _rfc3339(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

def _now_ms() -> int:
    return int(time.perf_counter() * 1000)

def _mk_req_id(thread_id: str) -> str:
    return f"{thread_id}:{_now_ms()}"

# ---------- LLMs ----------
_oai = OpenAIClient()

CODE_SYSTEM = """
You write a SINGLE Python cell to satisfy the TASK.

ENVIRONMENT & OUTPUT CONTRACT
- This environment captures ONLY STDOUT. Notebook "echo" does NOT show up.
- NEVER use `return` at top level. EVERYTHING you want me to see must be `print(...)`.
- Do NOT rely on display(), rich repr, or variable echo. Always `print(...)`.
- A directory named `outputs/` ALREADY EXISTS. You MUST save ALL files you create under `outputs/` (never anywhere else).
- Convenience variables are provided:
    - OUTPUTS_DIR: absolute path string to the outputs directory
    - INPUTS_DIR: absolute path string to the inputs directory
- When an artifact (file) is created under outputs/, immediately print its path on a line starting with EXACTLY:
    ARTIFACT: outputs/<relative_path_inside_outputs>
(If you used OUTPUTS_DIR to save, still print the RELATIVE path prefixed with `outputs/…`.)
- When printing required diagnostics, prefix each with the exact tag EVIDENCE: so they’re easy to parse:
    EVIDENCE: key=<name> value=<value_or_json>
- If required columns are unknown, print a schema preview first:
    EVIDENCE: schema=columns <comma_separated_column_names>
- If a required column is missing, STOP and print:
    ERROR: missing column '<name>'; available=<comma_separated_column_names>
(Do NOT fabricate; do NOT continue.)
- At the very end, print the sentinel:
    DONE
- If you recieve an s3:// path as input, you can assume it is downloaded under INPUTS_DIR/ and can be read by filename or by joining with INPUTS_DIR.

STYLE & SAFETY
- Be defensive: use try/except around I/O; on failure, `print("ERROR:", message)` and STOP.
- Prefer compact, parseable output. For tables, print `df.head(10).to_csv(index=False)` or `to_json(orient="records")` on a single line after `EVIDENCE:`.
- Do NOT print entire huge dataframes unless explicitly requested.
- Paths: read inputs by filename if present in CWD, or by joining with INPUTS_DIR. Write outputs ONLY under outputs/ (e.g., `open("outputs/foo.txt","w")` or `open(os.path.join(OUTPUTS_DIR,"foo.txt"),"w")`). Never write outside outputs/.

EXAMPLES (DO THIS)
>>> print("EVIDENCE: key=row_count value=", len(df))
>>> print("EVIDENCE: key=date_min value=", str(df['datum'].min()))
>>> print("EVIDENCE: key=unique_year_month value=", unique_df.to_json(orient="records"))
>>> df.to_csv("outputs/profile.csv", index=False)
>>> print("ARTIFACT: outputs/profile.csv")
>>> with open("outputs/profile_summary.md", "w", encoding="utf-8") as f:
...     f.write("# Profile Summary\\n...")
>>> print("ARTIFACT: outputs/profile_summary.md")
>>> print("DONE")

FORBIDDEN (DON'T DO THIS)
- `return results`
- Bare `df` / `df.head()` with no print
- `display(df)` or `from IPython.display import display`
- Writing files outside `outputs/` (e.g., directly in CWD or another folder)
"""

EVAL_SYSTEM = (
    "You evaluate and summarize code runs.\n"
    "Inputs (JSON): {task, stdout, stderr, files_out}\n"
    "Return ONE JSON object ONLY:\n"
    "{\n"
    '  "eval": "short reason (1-2 sentences)",\n'
    '  "verdict": "PASS" | "FAIL",\n'
    '  "output_summary": "<=800 chars summary of stdout (shapes, key columns, any wrote: lines); if stderr exists, include a 1-line gist>"\n'
    "}\n"
    "Rules:\n"
    "- Never invent columns or files.\n"
    "- Prefer concrete facts from stdout.\n"
    "- If stderr is non-empty, verdict is usually FAIL unless stdout clearly fulfilled the task."
)

code_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_CODE_MODEL","gpt-4.1-nano"),
    temperature=0.1,
    system=CODE_SYSTEM,
)
eval_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_EVAL_MODEL","gpt-4.1-nano"),
    temperature=0.0,
    system=EVAL_SYSTEM,
)

# ---------- Tools ----------
@mcp.tool()
async def exec_cell(
    input: CodeExecInput,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Execute a Python cell in the persistent kernel for thread_id based on code and a natural language task.

    CONTRACTED PATHS
    - Uploaded inputs are stored under: run_dir/inputs/
    - Generated artifacts MUST be saved under: run_dir/outputs/
    - Artifact collection & sync only consider files under outputs/

    Guidance:
    - Call once per user step. This tool is async; do not chain multiple exec_cell calls for the same thread_id in one turn
      (parallel calls are allowed only for different thread_ids).
    - Task format MUST be the following (no deviations), there shoudld not be s3 links in the task:
        TASK: <imperative action>
        EVIDENCE:
        - <bullet list>
        ARTIFACTS:
        - <files or 'none'>
    - Working directory: The session dir for thread_id. Read inputs via filename or by joining with INPUTS_DIR.
    - Inputs (files_in): If provided, the server downloads them into run_dir/inputs/ before code runs.
      Read by filename (CWD) or os.path.join(INPUTS_DIR, <name>).
    - Outputs (files_out): Only files under outputs/ are uploaded to S3 after execution. The response returns a list of {name, path, size}.
    - Dependencies (pip): Optional list of PyPI package specs to install before code runs.

    Args:
        input: CodeExecInput(
            thread_id: str
            task: str
            files_in: Optional[List[{
                name: str
                path: str  # usually S3 URI
                size: int
            }]] = []
            timeout_s: int = 300
            pip: Optional[List[str]] = None
            repair_attempts: int = 2
        )
        ctx: MCP Context for logging
    """
    req_id = _mk_req_id(input.thread_id)
    try:
        # Ensure kernel & directory layout (also injects INPUTS_DIR/OUTPUTS_DIR into globals)
        sandbox.get_kernel(input.thread_id)
        await ctx.info(f"[EXEC] thread={input.thread_id} tool args: {input.model_dump_json(indent=2)}")

        # Correlation IDs & timing
        t0 = time.perf_counter()
        await ctx.info(
            f"[EXEC_BEGIN] req_id={req_id} thread={input.thread_id} timeout_s={input.timeout_s} "
            f"repair_attempts={input.repair_attempts} pip={bool(input.pip)} "
            f"task_preview={repr((input.task or '')[:160])}"
        )

        # --------- Phase: download input files → run_dir/inputs/ ---------
        dl_start = time.perf_counter()
        local_files_in: List[Dict[str, Any]] = []
        dl_total_bytes = 0
        inputs_dir = _inputs_dir(input.thread_id)

        for file in (input.files_in or []):
            per_start = time.perf_counter()
            save_path = inputs_dir / file.name  # ensure all uploads live in inputs/
            save_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                full_path = f"{file.path}"
                s3c.download_file(full_path, save_path)
                size = (
                    file.size
                    if getattr(file, "size", None) is not None
                    else (save_path.stat().st_size if save_path.exists() else None)
                )
                local_files_in.append({
                    "name": file.name,
                    "path": str(save_path),  # absolute path (for logging); code can use INPUTS_DIR or filename
                    "size": size,
                })
                dl_total_bytes += int(size or 0)
                per_ms = int((time.perf_counter() - per_start) * 1000)
                await ctx.info(
                    f"[EXEC_PHASE] req_id={req_id} phase=download file={file.name} bytes={size} "
                    f"ms={per_ms} s3={file.path} -> inputs={save_path}"
                )
            except Exception as e:
                per_ms = int((time.perf_counter() - per_start) * 1000)
                log.error(
                    f"[EXEC_PHASE] req_id={req_id} phase=download file={file.name} ERROR={e} "
                    f"ms={per_ms} s3={file.path}"
                )
                # You may choose to raise here; currently we continue.

        dl_ms = int((time.perf_counter() - dl_start) * 1000)
        await ctx.info(
            f"[EXEC_PHASE] req_id={req_id} phase=download summary files={len(local_files_in)}/{len(input.files_in or [])} "
            f"bytes={dl_total_bytes} ms={dl_ms}"
        )

        # --------- Phase: execute cell (sandbox handles outputs/ scan & S3 sync) ---------
        exec_start = time.perf_counter()
        req = ExecRequest(
            code=None,  # code is generated by LLM from task
            language="python",
            files_in=local_files_in,
            timeout_s=input.timeout_s,
            task=input.task,
            pip=input.pip,
            use_llm_writer=True,
            repair_attempts=input.repair_attempts,
        )
        res = sandbox.exec_cell(thread_id=input.thread_id, req=req, code_llm=code_llm, eval_llm=eval_llm)
        exec_ms = int((time.perf_counter() - exec_start) * 1000)

        # --------- Wrap up ---------
        total_ms = int((time.perf_counter() - t0) * 1000)

        # Log files_out with details (only outputs/)
        files_out = res.files_out or []
        fo_count = len(files_out)
        fo_bytes = sum(int(f.get("size") or 0) for f in files_out)
        for f in files_out:
            await ctx.info(
                f"[EXEC_PHASE] req_id={req_id} phase=files_out name={f.get('name')} size={f.get('size')} path={f.get('path')}"
            )

        # Final summary log
        await ctx.info(
            f"[EXEC_END] req_id={req_id} thread={input.thread_id} ok={res.ok} "
            f"download_ms={dl_ms} exec_ms={exec_ms} total_ms={total_ms} "
            f"files_in={len(local_files_in)} files_out={fo_count} files_out_bytes={fo_bytes}"
        )

        # Return with metrics for the client to display
        return {
            "ok": res.ok,
            "code": res.code,            # {"filename":..., "text":...}
            "files_out": files_out,      # [{name, uri, size}, ...] (outputs/ only)
            "stdout": res.stdout or "",
            "summary": res.summary or "",
        }
    except Exception as e:
        log.exception(f"[EXEC_ERROR] req_id={req_id} thread={input.thread_id} ERROR={e}")
        return {
            "ok": False,
            "code": None,
            "files_out": [],
            "stdout": "",
            "summary": f"Execution error: {e}",
        }

@mcp.tool()
def list_artifacts(thread_id: str) -> Dict[str, Any]:
    """
    Return the artifact index (name, path, size) for the session, restricted to outputs/.
    """
    arts = sandbox._artifact_index(_run_dir(thread_id), only_under=sandbox.outputs_dirname)
    return {"artifacts": arts}

@mcp.tool()
def kill_session(thread_id: str, delete_files: bool = False) -> Dict[str, bool]:
    """
    Terminate the in-memory kernel; optionally delete the session directory.
    """
    sandbox._kernels.pop(thread_id, None)
    if delete_files:
        import shutil
        shutil.rmtree(_run_dir(thread_id), ignore_errors=True)
    return {"terminated": True}

# ---------- Entrypoint ----------

if __name__ == "__main__":
    log.info("Starting Sandbox MCP (HTTP) …")
    mcp.run(transport="streamable-http")  # or "sse" or "stdio"
