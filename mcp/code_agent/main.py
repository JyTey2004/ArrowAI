# mcp/code_agent/main.py
"""
Coding Agent main module.
This agent should take in a complex natural language coding task and iteratively plan and execute it in small steps.

Workflow:
1. Understand user goal.
2. Download input files to a session directory.
3. Loop:
    3.0 Plan next step using LLM (based on RUN_LOG.md so far and the user goal).
    3.1 Write a single Python cell to accomplish the step (LLM with CODE_SYSTEM).
    3.2 Execute the cell in a stateful Python kernel, capturing stdout/stderr
    3.3 Evaluate the execution (LLM with EVAL_SYSTEM).
    3.4 Append the plan, code, stdout/stderr, and artifacts to RUN_LOG.md.
    3.5 Repeat until TASK_COMPLETE, CLARIFY, max_steps, or error.
4. Return the final RUN_LOG.md and all artifacts.        
"""
from __future__ import annotations

import pathlib
import time
import os
import logging, sys
import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Context  # SDK's FastMCP, stdio-friendly
from components.executor import CodeSandbox, ExecRequest  # your code
from components.models import CodeExecInput
from components.artifacts_analyzer import ArtifactsAnalyzer
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
port = int(os.getenv("SANDBOX_PORT", "5000"))
path = os.getenv("SANDBOX_PATH", "/mcp/code_agent")
mcp = FastMCP("CodingSubagent", port=port, host=host, streamable_http_path=path)  # or transport="stdio" for stdio
sandbox = CodeSandbox(base_tmp_dir="tmp", s3_client=s3c)  # all I/O stays under tmp/
artifact_analyzer = ArtifactsAnalyzer(s3_client=s3c, base_tmp_dir="tmp")  # all I/O stays under tmp/

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
log = logging.getLogger("code-subagent")

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
- You are using a stateful Python kernel. Variables persist between cells. So do not repeat/restart from what's already been done.
- Read all provided CONTEXT carefully (CEL.md, task, all execution summary, artifacts and namespaces).
- NEVER use `return` at top level. EVERYTHING you want me to see must be `print(...)`.
- Do NOT rely on display(), rich repr, or variable echo. Always `print(...)`.
- A directory named `outputs/` ALREADY EXISTS. You MUST save ALL files you create under `outputs/` (never anywhere else).
- Convenience variables are provided:
    - OUTPUTS_DIR: absolute path string to the outputs directory
    - INPUTS_DIR: absolute path string to the inputs directory
- When an artifact (file) is created under outputs/, immediately print its path on a line starting with EXACTLY:
    ARTIFACT: outputs/<filename>
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
- If you recieve an s3:// path as input, you can assume it is downloaded under INPUTS_DIR/ and can be read by filename or by joining with INPUTS_DIR, `os.path.join(INPUTS_DIR, filename)`.
- Respect the artifact file descriptions, if any. 
- Prioritize using existing artifacts (in outputs/) over creating new ones.
STYLE & SAFETY
- Be defensive: use try/except around I/O; on failure, `print("ERROR:", message)` and STOP.
- Prefer compact, parseable output. For tables, print `df.head(10).to_csv(index=False)` or `to_json(orient="records")` on a single line after `EVIDENCE:`.
- Do NOT print entire huge dataframes unless explicitly requested.
- If you output a markdown, links and images will not render. Hence, use a pdf or html for reports, so you can embed images and links.  
- Paths: read inputs by filename if present in CWD, or by joining with INPUTS_DIR. Write outputs ONLY under outputs/ (e.g., `open("outputs/foo.txt","w")` or `open(os.path.join(OUTPUTS_DIR,"foo.txt"),"w")`). Never write outside outputs/.
"""

EVAL_SYSTEM = (
    "You evaluate and summarize code runs.\n"
    "Inputs (JSON): {task, stdout, stderr, code, all_files}\n"
    "Return ONE JSON object ONLY:\n"
    "{\n"
    '  "eval": "short reason (1-2 sentences)",\n'
    '  "verdict": "PASS" | "FAIL",\n'
    '  "output_summary": "A brief summary of the output, include key important information"\n'
    '  "artifacts": [ { "name": "file name", "description": "short description", "path": "s3://path/to/artifact" }, ... ]\n'
    '  "code_artifact": { "name": "file name", "description": "short description", "path": "s3://path/to/code_artifact" }\n'
    "}\n"
    "Rules:\n"
    "- Never invent columns or files.\n"
    "- Prefer concrete facts from stdout.\n"
    "- If stderr is non-empty, verdict is usually FAIL unless stdout clearly fulfilled the task."
    "- Add only relevant artifacts created in this run to the artifacts array. Return artifacts that the user expects to find. Output all pptx files found in outputs/.\n"
)

ARTIFACT_SYSTEM = (
    "You are a data scientist, find out all information in the file below relevant to the user's goal"
    "Be as specific and detailed as possible, extract all relevant information. Be specific about numbers, dates, names, places, and any other relevant details."
    "This information will be used by the planner and coding agent to decide what to do next."
    "If data contains tables, trends, or patterns, describe them in detail."
    "Output only bullet points and nothing else."
    f"You should provide the summary such that any coding agent can read this summary and understand the file and perform analysis/operations on it. "
    f"Provide the summary in a markdown bullet list without quotes. Include the artifact file path in the summary."
    "If the file path is s3://bucket/key, include whether it is in inputs/ or outputs/."
    f"In the summary, include column names and what do they represent. "
)

CONTEXT_SUMMARY_SYSTEM = (
    "You are an expert Software Engineer.\n"
    "You specialize in retaining as much context as possible about code execution.\n"
    
    "Contexts:\n"
    "  1. Refer to the All Execution Summary for a summary about all code execution steps.\n"
    "  2. Refer to the Last Execution for details about the last code execution step.\n\n"
    
    "Guidelines:\n"
    "- Your primary task is to include the Last Code Execution details in the All Execution Summary.\n"
    "- The All Execution Summary should be a comprehensive summary of all code execution steps taken so far,"
    " in as little words as possible, while retaining all key important details needed for next steps.\n"
    "- If there are unnecessary details in the All Execution Summary, you can remove them to make space for the Last Execution details.\n"
)

PLANNER_SYSTEM = (
    "You are a lead engineer at ArrowAI, overseeing task execution.\n"
    "You specialize in solving the user's request with a multi-step approach.\n"
    "Instruct the coding agent available to you to solve the user's request efficiently and proactively.\n\n"

    "You have access to a coding agent in a sandbox:\n"
    "- It takes in a natural language prompt and generates code to fulfill the request.\n"
    "- It can read/write files in the sandbox environment.\n"
    "- You should guide it with clear, specific instructions. Include what files to read/write and any other relevant details.\n\n"
    "Your goal is to complete the user's request by using it effectively.\n"
    "Start by understanding the complete situation before proposing solutions.\n"
    
    "Response Framework:\n"
    "  1. Extract what has been done from the All Execution Summary.\n"
    "  2. Read the User task to understand what's the end goal.\n"
    "  3. Review the Artifacts Metadata for useful information.\n"
    "  4. Identify the SINGLE next step to take towards completing the task.\n"
    "  5. Provide a DETAILED and SPECIFIC description of the step to the coding agent.\n"
    "  6. DO NOT write code yourself. The coding agent will handle code generation and execution.\n"
    "  7. Try not to ask the coding agent to log too much unnecessary information, only what is needed to understand progress and debug issues.\n"
    "  8. Always include the files to read/write and any other relevant details, from which folder, and to which folder.\n\n"
    "  9. When asking the agent to use/create files, always state the file's path, e.g. 'inputs/data.csv' or 'outputs/result.csv'.\n"

    "Guidelines:\n"
    "- Always choose only ONE next step. Break down complex tasks into smaller, manageable steps.\n"
    "- Ensure the step is clear and unambiguous, so the coding agent can execute it without further clarification.\n"
    "- If the next step is unclear or requires more information, respond with CLARIFY.\n"
    "- If the task is fully completed, respond with TASK_COMPLETE.\n"
    "- output RAW task description only"
    "- Avoid repeating previous steps or instructions already given to the coding agent.\n"
)


code_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_CODE_MODEL","gpt-4.1-mini"),
    temperature=0.0,
    system=CODE_SYSTEM,
)
eval_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_EVAL_MODEL","gpt-4.1-mini"),
    temperature=0.0,
    system=EVAL_SYSTEM,
)

artifact_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_ARTIFACT_MODEL","gpt-4.1-mini"),
    temperature=0.0,
    system=ARTIFACT_SYSTEM,
)

# ---------- Tools ----------
@mcp.tool()
async def code_orchestrate(
    input: CodeExecInput,
    ctx: Context,
) -> Dict[str, Any]:
    """
    Stateful coding subagent: plans and executes multi-step Python tasks (EDA, ETL, data cleaning, feature engineering, forecasting, time-series modeling, ML training/evaluation, report/plot generation, file I/O). Uses a persistent kernel; saves artifacts to outputs/; emits EVIDENCE/ARTIFACT lines; loops until TASK_COMPLETE/CLARIFY/max_steps.
    You may give this tool an extensive task, and it will break it down into smaller steps and execute them one by one.
    Args:
        - input: CodeExecInput(
            task="user goal / task",
            thread_id="unique ID for this coding thread",
            files_in=[  # files already available (e.g. downloaded from S3)
                {
                "name": "file name",
                "path": "full path of the file e.g s3://bucket/key",
                "description": "short description", # optional
                "size": 12345,  # optional  
                },
            ],
            timeout_s=300,  # per-cell execution timeout (default 300s)
            max_steps=7,  # max planning/execution steps (default 7)
            repair_attempts=1,  # if execution fails, how many times to try repairing
        )
        - ctx: The context for the code execution.

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
        artifact_log = ""

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
        
        # Understand the files input
        if local_files_in:
            artifact_log = await artifact_analyzer.analyze(input.thread_id, input.task or "", input.files_in, artifact_llm=artifact_llm, sandbox=sandbox, code_llm=code_llm, eval_llm=eval_llm)
            await ctx.info(f"[ORCH] analyzed {len(local_files_in)} input files")
        
        all_artifacts = local_files_in.copy()  # accumulate all artifacts here
        
        # Find all artifacts already in outputs/ (from prior runs)
        existing_arts = sandbox._artifact_index(_run_dir(input.thread_id), only_under=sandbox.outputs_dirname)
        if existing_arts:
            all_artifacts.extend(existing_arts)
            await ctx.info(f"[ORCH] found existing artifacts in outputs/: {len(existing_arts)} files")

        # -------- seed RUN_LOG once --------
        header = (
            f"# User task\n\n{input.task}\n\n"
            "## Input files\n\n" + "\n".join(f"- {f['name']} ({f['size']} bytes)" for f in local_files_in) + "\n\n---\n"
        )
        sandbox._append_cel_log(input.thread_id, header)

        # -------- loop --------
        step_idx = 0
        max_steps = getattr(input, "max_steps", 7) or 7
        completed = False
        need_clarification = False
        aggregated_files_out: List[Dict[str, Any]] = all_artifacts.copy()  # accumulate files_out across all steps
        new_files_out: List[Dict[str, Any]] = []  # files_out from the current step
        code_artifacts: Optional[Dict[str, Any]] = []
        last_res = None
        all_execution_summary = ""
        step_trace: List[Dict[str, Any]] = []

        while step_idx < max_steps and not (completed or need_clarification):
            step_idx += 1
            rl_path = sandbox.run_log_path(input.thread_id)
            run_log_txt = rl_path.read_text(encoding="utf-8", errors="ignore") if rl_path.exists() else "# Run Log\n\n"

            if step_idx > 1:
                # update the all_execution_summary with the last code execution details
                last_run_log = run_log_txt.rsplit("## Execute", 1)[-1] if "## Execute" in run_log_txt else run_log_txt
                last_code = last_res.code or {}
                
                context_prompt = (
                    f"User task:\n{input.task}\n\n"
                    f"All Execution Summary so far:\n{all_execution_summary}\n\n"
                    f"Last Execution details:\n{last_run_log}\n"
                    f"Last Execution Code:\n{last_code}\n"
                    f"Last Execution artifacts:\n" + "\n".join(f"- {a.name}: {a.description or ''}" for a in (last_res.files_out or [])) + "\n\n"
                )
                resp = _oai.generate(
                    model=os.getenv("SANDBOX_CONTEXT_MODEL", "gpt-4.1-mini"),
                    system=CONTEXT_SUMMARY_SYSTEM,
                    text=context_prompt,
                    temperature=0,
                )
                all_execution_summary = _oai.output_text(resp).strip()
                log.info(f"[ORCH] updated All Execution Summary {all_execution_summary}")
            
            task_prompt = (
                "Decide the SINGLE next step to execute now.\n"
                f"User task:\n{input.task}\n"
                f"Artifacts Metadata: {artifact_log}\n"
                f"All Execution Summary so far:\n{all_execution_summary}\n\n"
            )
            resp = _oai.generate(
                model=os.getenv("SANDBOX_PLANNER_MODEL", "gpt-4.1-mini"),
                system=PLANNER_SYSTEM,
                text=task_prompt,
                max_output_tokens=1200,
                temperature=0,
            )
            plan = _oai.output_text(resp).strip()
            sandbox._append_run_log(input.thread_id, f"\n\n## Execute {step_idx}")
            await ctx.info(f"[ORCH] step={step_idx} plan:\n{plan}")

            # early exits (strict equality)
            if "TASK_COMPLETE" in plan:
                completed = True
                sandbox._append_run_log(input.thread_id, f"**Result:** {plan}\n\n---\n")
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
                execution_context=all_execution_summary
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
                await artifact_analyzer.analyze(
                    input.thread_id, input.task or "", artifacts=step_files, artifact_llm=artifact_llm, sandbox=sandbox, code_llm=code_llm, eval_llm=eval_llm
                )
                for file_obj in step_files:
                    if file_obj not in aggregated_files_out:
                        aggregated_files_out.append(file_obj)
                        new_files_out.append(file_obj)
                    else:
                        # replace existing entry (e.g. to update size)
                        idx = aggregated_files_out.index(file_obj)
                        aggregated_files_out[idx] = file_obj
                        new_files_out.append(file_obj)
            
            curr_code = res.code or {}
            if curr_code:
                code_artifacts.append(curr_code)

            await ctx.info(f"[ORCH] step={step_idx} ok={res.ok} exec_ms={exec_ms} files_out={len(step_files)}")

        sandbox._append_cel_log(input.thread_id, f"All Execution Summary:\n{all_execution_summary}\n")
        final_cel = sandbox.cel_log_path(input.thread_id).read_text(encoding="utf-8", errors="ignore") if sandbox.cel_log_path(input.thread_id).exists() else ""

        # -------- final return (safe) --------
        final_ok = bool(last_res.ok) if last_res else completed
        

        return {
            "ok": final_ok,
            "files_out": new_files_out,
            "cel_log": final_cel or "",
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
def read_cel_log(thread_id: str, max_lines: int = 200) -> Dict[str, Any]:
    """
    Return the last max_lines lines of CEL.md for the session.
    """
    path = sandbox.cel_log_path(thread_id)
    if not path.exists():
        return {"cel_log": ""}
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    return {"cel_log": "\n".join(lines[-max_lines:])}

# @mcp.tool()
# def read_artifact(thread_id: str, name: str, max_bytes: int = 10000) -> Dict[str, Any]:
#     """
#     Return the content of an artifact file (if text-based and not too large). 
#     Args:
#         - thread_id: the coding session ID
#         - name: artifact file name (e.g. "outputs/foo.csv", must contain file extension)
#         - max_bytes: maximum bytes to read (default 10000)
#     """
#     # Limit file types to text-based ones
#     allowed_exts = {".txt", ".md", ".csv", ".tsv", ".json", ".log", ".py", ".ipynb"}
#     if not any(name.endswith(ext) for ext in allowed_exts):
#         return {"error": f"artifact '{name}' has unsupported file extension"}
#     artifact_local_path = None
#     short_file_path = ""
#     inputs_dir = artifact_analyzer._artifacts_dir(thread_id) / artifact_analyzer.inputs_dirname
#     outputs_dir = artifact_analyzer._artifacts_dir(thread_id) / artifact_analyzer.outputs_dirname

#     inp = (inputs_dir / name)
#     out = (outputs_dir / name)

#     if inp.is_file():
#         artifact_local_path = inp
#         short_file_path = f"{artifact_analyzer.inputs_dirname}/{name}"
#     elif out.is_file():
#         artifact_local_path = out
#         short_file_path = f"{artifact_analyzer.outputs_dirname}/{name}"
#     else:
#         return {"error": f"artifact '{name}' not found"}
    
#     try:
#         content = artifact_local_path.read_text(encoding="utf-8", errors="ignore") # Works for text, json, csv, md, py, ipynb, etc.
#         if len(content) > max_bytes:
#             content = content[:max_bytes] + f"\n\n... TRUNCATED to {max_bytes} bytes ..."
#         return {"name": name, "path": short_file_path, "content": content}
#     except Exception as e:
#         return {"error": f"artifact '{name}' read error: {e}"}
    
    

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
    log.info("Starting Code SubAgent MCP (HTTP) …")
    mcp.run(transport="streamable-http")  # or "sse" or "stdio"
