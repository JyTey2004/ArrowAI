from __future__ import annotations

import json
from pydantic import BaseModel, ValidationError

from app.models.orchestration.state import WSState
from app.utils.files.file_paths import cel_path
from app.utils.files.cel import read_cel
from app.utils.artifacts.view_formatting import add_view_urls, views_markdown
from app.services.openai_client import OpenAIClient

from app.core.logging import get_logger
logger = get_logger(__name__)

oai = OpenAIClient()

class ResponderOutput(BaseModel):
    answer: str          # markdown text (no fences)
    artifacts: list[str] # filenames only (no URLs)

RESPONDER_SYSTEM = (
    "You are a precise analyst. Read CEL.md, the task, and runtime outputs. "
    "Return a concise markdown answer in the 'answer' field (no code fences, no links)"
    "and a list of artifact filenames in the 'artifacts' field, that the user needs to see to understand the answer. Do not include unnecessary files. "
    "Output MUST be valid JSON that conforms to the provided JSON schema. "
    "Do not include any extra fields."
    "Json schema:\n"
    f"{ResponderOutput.model_json_schema()}"
)

def respond(state: WSState) -> WSState:
    """
    Use the CEL.md log, task, stdout/stderr, and artifacts to produce a final answer.
    The model returns strict JSON (ResponderOutput); we then append server-built view links.
    """
    run_id = state["run_id"]
    task = state["text"]
    base = state.get("base") or ""  # absolute base URL set by WS layer
    cel_snip = state.get("cel_snip") or read_cel(run_id)

    # Enrich current artifacts with absolute view URLs (server-built, not model-built)
    art_with_urls = add_view_urls(state.get("artifacts", []), run_id, base)
    views_md = views_markdown(art_with_urls, run_id, base)

    # Summarize runtime context for the model (no links here; we add them ourselves)
    summary = (
        f"Task:\n{task}\n\n"
        "Artifacts present:\n" +
        "\n".join(f"- {a.get('name','')} ({a.get('path','')})" for a in (state.get('artifacts') or []))
    )
    
    logger.info(f"Responder context for run_id={run_id}:\nCEL.md:\n{cel_snip}\n\nSummary:\n{summary}\n--- end summary ---\n\n")

    # Ask the model for JSON ONLY that matches the schema
    resp = oai.generate(
        model="gpt-4.1-mini",
        system=RESPONDER_SYSTEM,
        text="CEL.md (context):\n" + cel_snip + "\n\n" + summary,
        files=[str(cel_path(run_id))],
        temperature=0.2,
        max_output_tokens=800,
    )

    # Extract the JSON text and validate with Pydantic
    data_json = oai.output_text(resp)
    try:
        parsed = ResponderOutput.model_validate_json(data_json)
    except ValidationError:
        # Fail-soft fallback if the model somehow deviates
        parsed = ResponderOutput(answer="(Could not parse model output.)", artifacts=[])

    # Compose final answer: model's markdown + server-built links (so URLs are reliable)
    final_answer = parsed.answer.strip()
    if views_md.strip():
        final_answer += "\n\n### Used Artifacts\n" + views_md

    # Select only the artifacts referenced by the model (if any)
    selected_names = set(parsed.artifacts or [])
    selected_artifacts = [
        a for a in art_with_urls
        if not selected_names or a.get("name") in selected_names
    ]

    logger.info(f"Responder for run_id={run_id} produced answer with {selected_artifacts}.\n--- end answer ---\n\n")

    # Update state for WS/UI
    state["answer"] = final_answer
    state["answer_artifacts"] = selected_artifacts
    state["artifacts"] = selected_artifacts  # convenience: keep enriched artifacts with URLs
    return state
