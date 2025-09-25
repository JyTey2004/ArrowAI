from app.models.orchestration.state import WSState
from app.utils.files.cel import read_cel
from app.services.openai_client import OpenAIClient

from app.core.logging import get_logger
logger = get_logger(__name__)

oai = OpenAIClient()

CLARIFY_SYSTEM = (
    "You are a careful PM. Decide if the user's request needs clarification to proceed with execution.\n"
    "If clarification is needed, ask ONE concise question. If not, answer 'NO_CLARIFICATION_NEEDED'.\n"
)


def check_clarification(state: WSState) -> WSState:
    run_id, text = state["run_id"], state["text"].strip()
    cel_snip = read_cel(run_id)
    file_info = state.get("files", []) or []
    prompt = f"CEL.md (context):\n{cel_snip}\n\nUser task:\n{text}\n\nArtifacts uploaded:\n{file_info}\n\nDo we need clarification?"
    resp = oai.generate(model="gpt-4.1-mini", system=CLARIFY_SYSTEM, text=prompt, max_output_tokens=200, temperature=0)
    out = oai.output_text(resp).strip()
    need = out.upper() != "NO_CLARIFICATION_NEEDED"
    state["need_clarification"] = need
    if need:
        state["clarifying_question"] = out
    return state