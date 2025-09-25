from app.models.orchestration.state import WSState
from app.utils.files.cel import read_cel, append_cel
from app.services.openai_client import OpenAIClient

from app.core.logging import get_logger
logger = get_logger(__name__)

oai = OpenAIClient()

TODOS_SYSTEM = (
    "You are a delivery lead.\n"
    "Summarize the user's task into a deliverable goal at the top and a concise TODO list below.\n"
    "Break the task into a concise TODO list (markdown) of concrete, executable steps and deliverables.\n"
    "Each step should be a small, manageable action, with clear inputs and outputs. That can be done within a single cell of code.\n"
    "You may read CEL.md for context. Which will be the primary source of truth for previous tasks.\n"
    "Generate markdown only (no fences, no commentary)."
)

def write_todos(state: WSState) -> WSState:
    run_id = state["run_id"]
    cel_snip = read_cel(run_id)
    prompt = (
        "Write a TODO list for implementing the user's task.\n\n" +
        f"CEL.md (context):\n{cel_snip}\n\nUser task:\n{state['text']}\n"
    )
    resp = oai.generate(model="gpt-4.1-mini", system=TODOS_SYSTEM, text=prompt, max_output_tokens=600, temperature=0.2)
    todos = oai.output_text(resp).strip()
    state["todos_md"] = todos
    append_cel(run_id, "plan.todos", todos)
    return state
