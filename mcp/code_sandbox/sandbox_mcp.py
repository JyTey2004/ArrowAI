# mcp/sandbox/sandbox_mcp.py
from __future__ import annotations

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
mcp = FastMCP("CodingSubagent", port=port, host=host, mount_path=path)  # or transport="stdio" for stdio
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
- You are using a stateful Python kernel. Variables persist between cells. So read the prior code carefully, Do not repeat/restart from what's already been done.
- Always read the RUN_LOG file in the session dir for context on what has been done and what code has been written.
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

WRITER_SYSTEM = (
    "You are a senior consultant. Output ONLY one concrete task the coding agent will execute now.\n"
    "Max number of steps: 7.\n"
    "Do not repeat what was already done in prior steps in the RUN_LOG.md. (User could ask for a summary or a specific detail from previous steps.)\n"
    "CHUNKING POLICY:\n"
    "- Phase 'schema': If RUN_LOG.md lacks confirmed columns/dtypes and a parsed date col, emit a SMALL schema discovery task.\n"
    "- Phase 'pipeline': If schema is known, emit ONE MACRO TASK (single cell) that completes the user goal end-to-end.\n"
    "  If the goal is too complex, emit a SINGLE subtask that makes clear progress towards it.\n"
    "- Phase 'finalize': If the deliverable/artifact exists and deliverables are met, just output a single TASK_COMPLETE.\n"
    "Evidence contract: Each task must specify exact prints (e.g., shapes, columns, heads, counts).\n"
    "Artifact contract: If a file must be produced, name it and print its path + row count after writing. When user say something like 'show me a report', always think of it as an artifact request, and think of the most professional way to present it.\n"
    "If missing info blocks you, output exactly 'CLARIFY' together with the question. If the goal is met, output 'TASK_COMPLETE' and a clear summary of what was done in bullet points.\n"
    "Output format (no preface text):\n"
    "TASK: <imperative action>\n"
    "EVIDENCE:\n- <bullet list>\n"
    "ARTIFACTS:\n- <files or 'none'>\n"
)


code_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_CODE_MODEL","gpt-4.1-mini"),
    temperature=0.1,
    system=CODE_SYSTEM,
)
eval_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_EVAL_MODEL","gpt-4.1-mini"),
    temperature=0.0,
    system=EVAL_SYSTEM,
)

# ---------- Tools ----------
@mcp.tool(
    name="code_orchestrate",
    description=(
        "Stateful coding subagent: plans and executes multi-step Python tasks (EDA, ETL, data cleaning, "
        "feature engineering, forecasting, time-series modeling, ML training/evaluation, report/plot generation, "
        "file I/O). Uses a persistent kernel; saves artifacts to outputs/; emits EVIDENCE/ARTIFACT lines; "
        "loops until TASK_COMPLETE/CLARIFY/max_steps."
        "You may give this tool an extensive task, and it will break it down into smaller steps and execute them one by one."
    ),
)
async def orchestrate_eda_etl(
    input: CodeExecInput,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Executes general coding workflows in multiple small steps:
      1) Download inputs to run_dir/inputs/.
      2) Plan ONE next step from RUN_LOG.md using WRITER_SYSTEM.
      3) Execute a single Python cell (stateful kernel), capturing stdout/stderr/artifacts.
      4) Append the plan, stdout/stderr, and artifacts to RUN_LOG.md.
      5) Repeat until TASK_COMPLETE, CLARIFY, max_steps, or error.

    Returns ok, artifacts across ALL steps, and the tail of RUN_LOG.md.
    """
    req_id = _mk_req_id(input.thread_id)
    try:
        sandbox.get_kernel(input.thread_id)
        await ctx.info(f"[ORCH] thread={input.thread_id} args:\n{input.model_dump_json(indent=2)}")

        # -------- download inputs once --------
        dl_start = time.perf_counter()
        local_files_in: List[Dict[str, Any]] = []
        inputs_dir = _inputs_dir(input.thread_id)
        total_bytes = 0

        for f in (input.files_in or []):
            t1 = time.perf_counter()
            dst = inputs_dir / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                s3c.download_file(f.path, dst)
                size = f.size if getattr(f, "size", None) is not None else (dst.stat().st_size if dst.exists() else None)
                local_files_in.append({"name": f.name, "path": str(dst), "size": size})
                total_bytes += int(size or 0)
                await ctx.info(f"[ORCH] downloaded file={f.name} bytes={size} ms={int((time.perf_counter()-t1)*1000)} -> {dst}")
            except Exception as e:
                await ctx.error(f"[ORCH] download error file={f.name} s3={f.path} err={e}")

        dl_ms = int((time.perf_counter() - dl_start) * 1000)
        await ctx.info(f"[ORCH] download summary files={len(local_files_in)}/{len(input.files_in or [])} bytes={total_bytes} ms={dl_ms}")

        # -------- seed RUN_LOG once --------
        header = (
            f"# User task\n\n{input.task}\n\n"
            "## Input files\n\n" + "\n".join(f"- {f['name']} ({f['size']} bytes)" for f in local_files_in) + "\n\n---\n"
        )
        sandbox._append_run_log(input.thread_id, header)

        # -------- loop --------
        step_idx = 0
        max_steps = getattr(input, "max_steps", 7) or 7
        completed = False
        need_clarification = False
        aggregated_files_out: List[Dict[str, Any]] = []
        last_res = None

        while step_idx < max_steps and not (completed or need_clarification):
            step_idx += 1
            rl_path = sandbox.run_log_path(input.thread_id)
            run_log_txt = rl_path.read_text(encoding="utf-8", errors="ignore") if rl_path.exists() else "# Run Log\n\n"

            task_prompt = (
                "Decide the SINGLE next step to execute now.\n"
                "If the RUN_LOG.md does not already show confirmed columns/dtypes and a parsed date column, you MUST pick a schema discovery task.\n"
                "If information is missing and you cannot proceed, output exactly 'CLARIFY'.\n"
                "If the user goal is met, output exactly 'TASK_COMPLETE'.\n"
                "Remember the Evidence & Artifacts contracts.\n\n"
                f"RUN_LOG.md:\n{run_log_txt}\n\n"
                f"User task:\n{input.task}\n"
            )
            resp = _oai.generate(
                model=os.getenv("SANDBOX_PLANNER_MODEL", "gpt-4.1-mini"),
                system=WRITER_SYSTEM,  # now references RUN_LOG.md
                text=task_prompt,
                max_output_tokens=1200,
                temperature=0.1,
            )
            plan = _oai.output_text(resp).strip()
            sandbox._append_run_log(input.thread_id, f"## Execute {step_idx} — Plan\n\n{plan}\n\n")
            await ctx.info(f"[ORCH] step={step_idx} plan:\n{plan}")

            # early exits (strict equality)
            if plan == "TASK_COMPLETE":
                completed = True
                sandbox._append_run_log(input.thread_id, "**Result:** TASK_COMPLETE\n\n---\n")
                await ctx.info(f"[ORCH] step={step_idx} TASK_COMPLETE (no execution)")
                break
            if plan == "CLARIFY":
                need_clarification = True
                sandbox._append_run_log(input.thread_id, "**Result:** CLARIFY\n\n")
                await ctx.info(f"[ORCH] step={step_idx} CLARIFY (no execution)")
                break

            # execute single cell
            t_exec = time.perf_counter()
            req = ExecRequest(
                code=None,
                language="python",
                files_in=local_files_in,
                timeout_s=input.timeout_s,
                task=plan,
                use_llm_writer=True,
                repair_attempts=input.repair_attempts,
            )
            res = sandbox.exec_cell(
                thread_id=input.thread_id,
                req=req,
                code_llm=code_llm,
                eval_llm=eval_llm,
            )
            last_res = res
            exec_ms = int((time.perf_counter() - t_exec) * 1000)

            # log stdout/stderr + artifacts into RUN_LOG.md
            # stdout = res.stdout or ""
            # sandbox._append_run_log(input.thread_id, f"### Stdout (step {step_idx})\n\n```\n{stdout}\n```\n\n")
            if getattr(res, "stderr", None):
                sandbox._append_run_log(input.thread_id, f"### Stderr (step {step_idx})\n\n```\n{res.stderr}\n```\n\n")

            step_files = res.files_out or []
            if step_files:
                aggregated_files_out.extend(step_files)
                bullets = "\n".join([f"- **{f.get('name')}** — {f.get('size')} bytes — {f.get('path')}" for f in step_files])
                sandbox._append_run_log(input.thread_id, f"### Artifacts (step {step_idx})\n\n{bullets}\n\n")

            await ctx.info(f"[ORCH] step={step_idx} ok={res.ok} exec_ms={exec_ms} files_out={len(step_files)}")

        # -------- final return (safe) --------
        final_ok = bool(last_res.ok) if last_res else completed
        final_run_log = sandbox.run_log_path(input.thread_id).read_text(encoding="utf-8", errors="ignore") if sandbox.run_log_path(input.thread_id).exists() else "# Run Log\n\n"

        return {
            "ok": final_ok,
            "files_out": aggregated_files_out,
            "run_log": final_run_log[-1024:] or "",
            "steps_executed": step_idx,
            "completed": completed,
            "need_clarification": need_clarification,
        }
    except Exception as e:
        log.exception(f"[ORCH_ERROR] req_id={req_id} thread={input.thread_id} ERROR={e}")
        return {
            "ok": False,
            "files_out": [],
            "run_log": "",
            "steps_executed": 0,
            "completed": False,
            "need_clarification": False,
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
