from app.models.orchestration.state import WSState
from app.utils.files.cel import read_cel, append_cel, cel_path
from app.services.openai_client import OpenAIClient
from app.tools.sandbox.executor import ExecRequest
from app.tools.sandbox import sandbox, code_llm, eval_llm

from app.core.logging import get_logger

logger = get_logger(__name__)

oai = OpenAIClient()

WRITER_SYSTEM = (
    "You are a senior consultant. Output ONLY one concrete task the coding agent will execute now.\n"
    "Max number of steps: 7.\n"
    "CHUNKING POLICY:\n"
    "- Phase 'schema': If CEL.md lacks confirmed columns/dtypes and a parsed date col, emit a SMALL schema discovery task.\n"
    "- Phase 'pipeline': If schema is known, emit ONE MACRO TASK (single cell) that completes the user goal end-to-end.\n"
        "If the goal is too complex, emit a SINGLE subtask that makes clear progress towards it.\n"
    "- Phase 'finalize': If the deliverable/artifact exists and deliverables are met, just output a single TASK_COMPLETE.\n"
    "Evidence contract: Each task must specify exact prints (e.g., shapes, columns, heads, counts).\n"
    "Artifact contract: If a file must be produced, name it and print its path + row count after writing.\n"
    "Output format (no preface text):\n"
    "TASK: <imperative action>\n"
    "EVIDENCE:\n- <bullet list>\n"
    "ARTIFACTS:\n- <files or 'none'>\n"
)


def execute(state: WSState) -> WSState:
    run_id = state["run_id"]
    step_idx = int(state.get("step_idx", 0))
    max_steps = int(state.get("max_steps", 7))
    
    # 3.0 LLM plans next step based on CEL
    cel_snip = read_cel(run_id)
    task_prompt = (
        "Decide the SINGLE next step to execute now.\n"
        "If the CEL.md does not already show confirmed columns/dtypes and a parsed date column, you MUST pick a schema discovery task.\n"
        "You may clarify if there is missing information, an agent will clarify based on the CEL.md. Output exactly 'CLARIFY'\n"
        "If the user goal is met, output exactly 'TASK_COMPLETE'.\n"
        "Remember the Evidence & Artifacts contracts.\n\n"
        f"CEL.md:\n{cel_snip}\n\n"
        f"User task:\n{state['text']}\n"
    )
    resp = oai.generate(model="gpt-4.1-mini", system=WRITER_SYSTEM, text=task_prompt,
                        files=[str(cel_path(run_id))], max_output_tokens=2000, temperature=0.1)
    task = oai.output_text(resp).strip()
    
    logger.info(f"Execute node for run_id={run_id}, step_idx={step_idx} decided task:\n{task}\n--- end task ---\n\n")

    if "CLARIFY" in task:
        state["done"] = True
        state["need_clarification"] = True
        return state

    state["task"] = task
    
    if "TASK_COMPLETE" in task:
        state["done"] = True
        append_cel(run_id, f"Execute {step_idx+1}:", "TASK_COMPLETE\n")
        return state
    else:
        append_cel(run_id, f"Execute {step_idx+1}:", f"{task}\n")

    # 3.2 Execute in sandbox
    req = ExecRequest(code=None, timeout_s=120, task=task, use_llm_writer=True)
    res = sandbox.exec_cell(run_id, req, code_llm=code_llm, eval_llm=eval_llm)

    state["stdout"], state["stderr"], state["artifacts"] = res.stdout, res.stderr, res.files_out
    
    logger.info(f"Execute node for run_id={run_id}, step_idx={step_idx} got stdout:\n{res.stdout}\n--- end stdout ---\n\n")

    if res.code:
        state["code"] = res.code

    # loop control
    step_idx += 1
    state["step_idx"] = step_idx
    # Heuristic: stop if stderr empty and step_idx hit max else continue
    done = (step_idx >= max_steps) and not res.stderr
    state["done"] = done
    return state