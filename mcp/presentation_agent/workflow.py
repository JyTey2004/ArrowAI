"""
LangGraph workflow for the presentation agent.

This module orchestrates the end-to-end presentation workflow:
1. Plan an outline from the narrative brief and artifacts.
2. Delegate quantitative analysis to the code agent for each slide.
3. Draft PEEL slides leveraging the generated evidence.
4. Assemble the deck artifact once all slides are prepared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from components.models import (
    DataAsset,
    OutlineArtifact,
    PresentationAssemblyRequest,
    PresentationAssemblyResponse,
    PresentationOutlineRequest,
    PresentationOutlineResponse,
    PresentationWorkflowRequest,
    SlideArtifact,
    SlideDraft,
    SlideDraftRequest,
    SlideDraftResponse,
)

# Public alias for code agent caller used in config
CodeAgentCaller = Callable[..., Awaitable[Dict[str, Any]]]


class SlideSkeleton(TypedDict, total=False):
    slide_id: str
    beat: str
    title_stub: str
    expected_evidence: List[str]
    outline_metadata: Dict[str, Any]
    bound_artifacts: List[Any]
    insight_summary: Optional[str]
    code_run: Optional[Dict[str, Any]]
    draft_reference: Optional[Dict[str, Any]]
    evaluation_notes: Optional[str]


@dataclass
class PresentationState:
    """
    Aggregate state that flows through the LangGraph.

    The state captures the narrative inputs, data assets, intermediate results
    returned by the code agent, slide drafts, and final export metadata.
    """

    workflow_request: Optional[PresentationWorkflowRequest] = None
    outline_request: Optional[PresentationOutlineRequest] = None
    outline_response: Optional[PresentationOutlineResponse] = None

    thread_id: str = ""
    narrative_brief: str = ""
    research_context: str = ""

    data_assets: List[DataAsset] = field(default_factory=list)
    outline_artifacts: List[OutlineArtifact] = field(default_factory=list)

    beats: List[Dict[str, Any]] = field(default_factory=list)
    slide_skeleton: List[SlideSkeleton] = field(default_factory=list)

    artifacts_index: Dict[str, List[dict]] = field(default_factory=dict)
    insights: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    slide_drafts: Dict[str, SlideDraftResponse] = field(default_factory=dict)
    deck_response: Optional[PresentationAssemblyResponse] = None

    iteration: int = 0
    max_iterations: int = 1
    ready_for_export: bool = False

    code_timeout: int = 300
    code_max_steps: int = 5


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _resolve_outline_request(state: PresentationState) -> PresentationOutlineRequest:
    if state.outline_request:
        return state.outline_request

    if state.workflow_request:
        req = PresentationOutlineRequest(
            topic=state.workflow_request.topic,
            audience=state.workflow_request.audience,
            desired_outcome=state.workflow_request.desired_outcome,
            slide_count_hint=state.workflow_request.slide_count_hint,
            include_appendix=state.workflow_request.include_appendix,
            artifacts=state.workflow_request.outline_artifacts,
        )
    else:
        req = PresentationOutlineRequest(topic=state.narrative_brief or "Untitled presentation")

    state.outline_request = req
    return req


def _format_assets_for_prompt(assets: List[DataAsset]) -> str:
    if not assets:
        return "- No structured datasets provided; rely on qualitative context."

    lines = []
    for asset in assets:
        descr = asset.description or "No description"
        lines.append(f"- {asset.name}: {descr} (source {asset.path})")
    return "\n".join(lines)


def _build_insight_task_prompt(state: PresentationState, slide: SlideSkeleton) -> str:
    title = slide.get("title_stub") or slide.get("beat") or "Unnamed slide"
    beat = slide.get("beat") or "General"
    research_context = state.research_context or (
        state.workflow_request.research_context if state.workflow_request else ""
    )
    expected_evidence = slide.get("expected_evidence") or []
    evidence_text = ", ".join(expected_evidence) if expected_evidence else "the strongest quantitative proof available"
    assets_text = _format_assets_for_prompt(state.data_assets)

    return (
        f"You are assisting the presentation team with slide '{title}' in the '{beat}' beat.\n"
        f"Thread ID: {state.thread_id}\n\n"
        f"Goal: Derive quantified story points and produce visual artifacts that support this slide's conclusion.\n"
        f"Focus evidence on: {evidence_text}.\n\n"
        f"Research context (cite when relevant):\n{research_context or 'No qualitative context supplied.'}\n\n"
        f"Available datasets already staged in the sandbox:\n{assets_text}\n\n"
        "Execution contract:\n"
        "- Use the provided datasets under INPUTS_DIR; do not fetch external sources.\n"
        "- Compute decision-grade metrics (deltas, trends, regressions, cohorts) that underpin the headline.\n"
        "- Generate at least one publication-ready chart or table per key metric and save under outputs/ with descriptive filenames.\n"
        "- Log each key metric using `EVIDENCE:` and register generated files with `ARTIFACT:`.\n"
        "- Finish with `DONE`.\n"
        "- Keep the sandbox session alive for downstream slide drafting.\n"
    )


def _to_slide_artifacts(files_out: List[dict]) -> List[SlideArtifact]:
    artifacts: List[SlideArtifact] = []
    for idx, file_info in enumerate(files_out or []):
        try:
            artifacts.append(
                SlideArtifact(
                    name=file_info.get("name") or f"artifact_{idx}",
                    path=file_info.get("path"),
                    description=file_info.get("description"),
                    artifact_type=file_info.get("type"),
                    is_primary=(idx == 0),
                )
            )
        except Exception:
            # Skip malformed entries but continue processing others
            continue
    return artifacts


# --------------------------------------------------------------------------- #
# LangGraph nodes
# --------------------------------------------------------------------------- #

async def narrative_to_beats_node(state: PresentationState, config: Dict[str, Any]) -> PresentationState:
    planner = config.get("outline_planner")
    if planner is None or (state.outline_response and state.slide_skeleton):
        return state

    outline_request = _resolve_outline_request(state)
    outline = planner.plan_outline(outline_request)

    state.outline_response = outline
    state.narrative_brief = outline_request.topic
    state.iteration = 0
    state.ready_for_export = False

    beat_counts: Dict[str, int] = {}
    skeleton: List[SlideSkeleton] = []

    for slide in outline.slides:
        beat_counts[slide.beat] = beat_counts.get(slide.beat, 0) + 1
        skeleton.append(
            SlideSkeleton(
                slide_id=slide.slide_id,
                beat=slide.beat,
                title_stub=slide.title,
                expected_evidence=slide.expected_evidence or [],
                outline_metadata=slide.model_dump(),
                bound_artifacts=[],
            )
        )

    state.beats = [{"name": beat, "target_slides": count} for beat, count in beat_counts.items()]
    state.slide_skeleton = skeleton
    return state


async def evidence_binding_node(state: PresentationState, config: Dict[str, Any]) -> PresentationState:
    call_code_agent: Optional[CodeAgentCaller] = config.get("call_code_agent")
    logger = config.get("logger")

    if call_code_agent is None:
        return state

    for slide in state.slide_skeleton:
        slide_id = slide.get("slide_id") or "unknown"
        if slide.get("insight_summary"):
            continue  # already processed

        prompt = _build_insight_task_prompt(state, slide)
        try:
            response = await call_code_agent(
                prompt,
                state.thread_id,
                state.data_assets,
                timeout=state.code_timeout,
                max_steps=state.code_max_steps,
            )
        except Exception as exc:  # pragma: no cover - defensive
            if logger:
                logger.exception("Code agent execution failed for slide %s: %s", slide_id, exc)
            slide["evaluation_notes"] = f"Code agent error: {exc}"
            continue

        state.insights[slide_id] = response
        summary = response.get("cel_log") or response.get("summary") or ""
        slide["insight_summary"] = summary or "No quantitative summary produced."

        files_out = response.get("files_out") or []
        artifacts = _to_slide_artifacts(files_out)
        slide["bound_artifacts"] = artifacts
        state.artifacts_index[slide_id] = files_out
        slide["code_run"] = {
            "ok": response.get("ok", False),
            "steps_executed": response.get("steps_executed"),
            "need_clarification": response.get("need_clarification"),
        }

    return state


async def draft_slides_node(state: PresentationState, config: Dict[str, Any]) -> PresentationState:
    writer = config.get("slide_writer")
    if writer is None:
        return state

    for slide in state.slide_skeleton:
        slide_id = slide.get("slide_id")
        if not slide_id or slide_id in state.slide_drafts:
            continue

        insight_summary = slide.get("insight_summary") or state.research_context or "No insight summary available."
        artifacts = slide.get("bound_artifacts") or []
        slide_artifacts = []
        for artifact in artifacts:
            if isinstance(artifact, SlideArtifact):
                slide_artifacts.append(artifact)
            else:
                try:
                    slide_artifacts.append(SlideArtifact(**artifact))
                except Exception:
                    continue

        request = SlideDraftRequest(
            section_title=slide.get("title_stub") or slide.get("beat") or "Slide",
            thread_id=state.thread_id,
            insight_summary=insight_summary,
            key_points=slide.get("expected_evidence") or [],
            artifacts=slide_artifacts,
            slide_identifier=slide_id,
            tone="formal",
        )

        response: SlideDraftResponse = writer.draft_slide(request)
        state.slide_drafts[slide_id] = response
        slide["draft_reference"] = response.model_dump()

    return state


async def evaluate_slides_node(state: PresentationState, config: Dict[str, Any]) -> PresentationState:
    state.iteration += 1
    remaining = []

    for slide in state.slide_skeleton:
        slide_id = slide.get("slide_id")
        if slide_id and slide_id in state.slide_drafts:
            slide["evaluation_notes"] = "Draft ready for review."
        else:
            slide["evaluation_notes"] = "Draft pending."
            remaining.append(slide_id)

    state.ready_for_export = not remaining
    return state


async def export_deck_node(state: PresentationState, config: Dict[str, Any]) -> PresentationState:
    assembler = config.get("deck_assembler")
    if assembler is None or state.deck_response is not None:
        state.ready_for_export = True
        return state

    slides: List[SlideDraft] = [
        state.slide_drafts[slide["slide_id"]].slide
        for slide in state.slide_skeleton
        if slide.get("slide_id") in state.slide_drafts
    ]

    request = PresentationAssemblyRequest(
        slides=slides,
        format="markdown",
        thread_id=state.thread_id or None,
    )
    deck_response = assembler.assemble(request)
    state.deck_response = deck_response
    state.ready_for_export = True
    return state


def route_after_evaluation(state: PresentationState) -> Literal["continue", "export"]:
    if state.ready_for_export:
        return "export"
    if state.iteration >= state.max_iterations:
        return "export"
    return "continue"


# --------------------------------------------------------------------------- #
# Graph builder
# --------------------------------------------------------------------------- #

def build_presentation_graph() -> Any:
    graph_builder = StateGraph(PresentationState)
    graph_builder.add_node("narrative_to_beats", narrative_to_beats_node)
    graph_builder.add_node("evidence_binding", evidence_binding_node)
    graph_builder.add_node("draft_slides", draft_slides_node)
    graph_builder.add_node("evaluate_slides", evaluate_slides_node)
    graph_builder.add_node("export_deck", export_deck_node)

    graph_builder.add_edge(START, "narrative_to_beats")
    graph_builder.add_edge("narrative_to_beats", "evidence_binding")
    graph_builder.add_edge("evidence_binding", "draft_slides")
    graph_builder.add_edge("draft_slides", "evaluate_slides")
    graph_builder.add_conditional_edges(
        "evaluate_slides",
        route_after_evaluation,
        {"continue": "evidence_binding", "export": "export_deck"},
    )
    graph_builder.add_edge("export_deck", END)

    return graph_builder.compile()


__all__ = [
    "CodeAgentCaller",
    "SlideSkeleton",
    "PresentationState",
    "build_presentation_graph",
    "narrative_to_beats_node",
    "evidence_binding_node",
    "draft_slides_node",
    "evaluate_slides_node",
    "export_deck_node",
]
