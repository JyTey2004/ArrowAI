"""
Presentation agent entry point.

This module exposes MCP tools for outline planning, insight generation,
slide drafting, deck assembly, and an end-to-end LangGraph workflow that
co-operates with the code agent.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import pathlib
import sys
import textwrap
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.server.fastmcp import Context, FastMCP

from components.models import (
    DataAsset,
    GenerateSlideRequest,
    GenerateSlideResponse,
    InsightGenerationRequest,
    InsightGenerationResponse,
    LayoutSpecification,
    PresentationAssemblyRequest,
    PresentationAssemblyResponse,
    PresentationOutlineRequest,
    PresentationOutlineResponse,
    PresentationWorkflowRequest,
    PresentationWorkflowResponse,
    SlideArtifact,
    SlideDraftRequest,
    SlideDraftResponse,
    SlideQAReport,
)
from components.outline import PresentationOutlinePlanner
from components.qa import SlideQAAgent
from aws import S3Client
from services.openai_client import OpenAIClient
from utils.LLMAdapter import LLMAdapter

from utils.aggregate_slides import assemble_pptx_from_directory


def _setup_logging() -> logging.Logger:
    level = os.getenv("PRESENTATION_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("mcp").setLevel(logging.INFO)
    return logging.getLogger("presentation-agent")


log = _setup_logging()

HOST = os.getenv("PRESENTATION_HOST", "127.0.0.1")
PORT = int(os.getenv("PRESENTATION_PORT", "5004"))
PATH = os.getenv("PRESENTATION_PATH", "/mcp/presentation_agent")
DEFAULT_BUCKET = os.getenv("MCP_BUCKET", "arrowai")
REGION = os.getenv("AWS_REGION", "ap-southeast-1")
TMP_DIR = os.getenv("PRESENTATION_TMP_DIR", "tmp")

QA_MODEL = os.getenv("PRESENTATION_QA_MODEL", "gpt-4.1-mini")
QA_TEMPERATURE = float(os.getenv("PRESENTATION_QA_TEMPERATURE", "0.0"))

CODE_AGENT_TIMEOUT = int(os.getenv("PRESENTATION_CODE_TIMEOUT", "300"))
CODE_AGENT_MAX_STEPS = int(os.getenv("PRESENTATION_CODE_MAX_STEPS", "5"))

QA_SYSTEM = """You are a slide formatting QA inspector, for McKinsey & Company, building consultant grade slides.
You are given an image of a slide and metadata about its layout and content.
Analyse the provided slide image and metadata to detect layout, alignment, overflow, or styling issues.
Respond strictly with JSON following this schema:
{
  "status": "PASS" | "NEEDS_FIX",
  "score": 0-100,
  "issues": [
    {"code": str, "target": str, "detail": str}
  ],
  "patch": {
    ... optional remediation instructions ...
  }
}
Rules:
- If no blocking issues are found, return status PASS and an empty issues array.
- When issues exist, fill detail with actionable descriptions and provide a patch block when possible.
- Never include commentary outside the JSON object.
"""

mcp = FastMCP(
    "PresentationAgent",
    port=PORT,
    host=HOST,
    streamable_http_path=PATH,
)

CODE_AGENT_MCP_WS = os.environ.get("CODE_AGENT_MCP_WS", "http://localhost:5000/mcp/code_agent")

_mcp_client: Optional[MultiServerMCPClient] = None
_mcp_client_lock = asyncio.Lock()
_tool_index: Dict[str, BaseTool] = {}
_tools_ready = asyncio.Lock()


async def mcp_client() -> MultiServerMCPClient:
    """Initialise (if needed) and return the shared MCP client."""
    global _mcp_client
    async with _mcp_client_lock:
        if _mcp_client is None:
            _mcp_client = MultiServerMCPClient(
                {
                    "code_agent": {
                        "url": CODE_AGENT_MCP_WS,
                        "transport": "streamable_http",
                    }
                }
            )
            log.info("MultiServerMCPClient initialised.")
    if _mcp_client is None:
        raise RuntimeError("MultiServerMCPClient failed to initialise.")
    return _mcp_client


async def _ensure_tools_loaded() -> None:
    if _tool_index:
        return
    async with _tools_ready:
        if _tool_index:
            return
        client = await mcp_client()
        tools = await client.get_tools()
        for tool in tools:
            name = getattr(tool, "name", None)
            if name:
                _tool_index[name] = tool
        log.info("Loaded %d tool(s) from code agent.", len(_tool_index))


async def _ensure_tool(name: str) -> BaseTool:
    await _ensure_tools_loaded()
    tool = _tool_index.get(name)
    if tool is None:
        raise RuntimeError(f"Required tool '{name}' not available from code agent.")
    return tool


def _run_dir(thread_id: str) -> pathlib.Path:
    return pathlib.Path(TMP_DIR).resolve() / thread_id

def _slide_log(thread_id: str, slide_id: str) -> pathlib.Path:
    return _run_dir(thread_id) / f"SLIDE_LOG_{slide_id}.md"

def _append_slide_log(thread_id: str, entry: str, slide_id: str) -> None:
    log_path = _slide_log(thread_id, slide_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = f"## {thread_id}\n\n"
    prev = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else header
    log_path.write_text(prev + entry + "\n", encoding="utf-8")

def _presentation_dir(thread_id: str) -> pathlib.Path:
    # make dir if needed
    dir_path = _run_dir(thread_id) / "presentations"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def _format_files_in(data_assets: Optional[Sequence[DataAsset]]) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for asset in data_assets or []:
        file_payload: Dict[str, Any] = {
            "name": asset.name,
            "path": asset.path,
        }
        if asset.description:
            file_payload["description"] = asset.description
        if asset.size is not None:
            file_payload["size"] = asset.size
        files.append(file_payload)
    return files


def _find_artifact_path(response: Dict[str, Any], expected_name: str) -> Optional[str]:
    files_out = response.get("files_out") or []
    expected_lower = expected_name.lower()
    for artifact in files_out:
        name = (artifact.get("name") or "").split("/")[-1].lower()
        path = artifact.get("path") or ""
        path_tail = path.split("/")[-1].lower() if path else ""
        if expected_lower in {name, path_tail}:
            return path
    return None


def _read_artifact(path: str) -> str:
    if not path:
        raise ValueError("Artifact path was empty.")
    if path.startswith("s3://"):
        data, _ = s3_client.get_bytes(path)
        if path.split("/")[-1].lower().endswith((".json", ".txt", ".md", ".csv", ".tsv", ".xml", ".html")):
            return data.decode("utf-8")
        return data
    local_path = os.path.join(TMP_DIR, path)
    if os.path.isfile(local_path):
        with open(local_path, "r", encoding="utf-8") as fh:
            return fh.read()
    raise ValueError(f"Artifact path '{path}' is not accessible from presentation agent.")


def _load_json_artifact(response: Dict[str, Any], expected_name: str) -> Dict[str, Any]:
    artifact_path = _find_artifact_path(response, expected_name)
    if not artifact_path:
        raise ValueError(f"Expected artifact '{expected_name}' not produced by code agent.")
    payload = _read_artifact(artifact_path)
    return json.loads(payload)


def _load_json_from_path(path: str) -> Dict[str, Any]:
    data = _get_artifact_bytes(path)
    return json.loads(data.decode("utf-8"))


def _json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _get_artifact_bytes(path: str) -> bytes:
    if not path:
        raise ValueError("Artifact path was empty.")
    if path.startswith("s3://"):
        data, _ = s3_client.get_bytes(path)
        return data
    local_path = os.path.join(TMP_DIR, path)
    if os.path.isfile(local_path):
        with open(local_path, "rb") as fh:
            return fh.read()
    raise ValueError(f"Artifact path '{path}' is not accessible from presentation agent.")


def _update_artifact_map(store: Dict[str, str], response: Dict[str, Any]) -> None:
    for file_info in response.get("files_out") or []:
        candidate = file_info.get("path") or file_info.get("name") or ""
        if candidate:
            store[os.path.basename(candidate)] = candidate


async def call_code_agent(
    *,
    tool_name: str = "code_orchestrate",
    task: Optional[str] = None,
    thread_id: str,
    data_assets: Optional[Sequence[DataAsset]] = None,
    timeout: Optional[int] = None,
    max_steps: Optional[int] = None,
    repair_attempts: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Invoke a specific tool on the coding agent."""
    tool = await _ensure_tool(tool_name)
    default_thread = thread_id

    if tool_name == "code_orchestrate":
        if not task:
            raise ValueError("Task description is required for code_orchestrate.")
        exec_payload = {
            "thread_id": default_thread,
            "task": textwrap.dedent(task).strip(),
            "timeout_s": timeout or CODE_AGENT_TIMEOUT,
            "max_steps": max_steps or CODE_AGENT_MAX_STEPS,
            "repair_attempts": repair_attempts if repair_attempts is not None else 1,
            "files_in": _format_files_in(data_assets),
        }
        log.debug("Dispatching task to code agent (thread=%s).", exec_payload["thread_id"])
        return await tool.ainvoke({
            "input": exec_payload
        })

    if payload is None:
        raise ValueError(f"Payload is required for tool '{tool_name}'.")

    request_payload = dict(payload)
    request_payload.setdefault("thread_id", default_thread)
    log.debug("Dispatching tool '%s' to code agent (thread=%s).", tool_name, request_payload["thread_id"])
    return await tool.ainvoke(request_payload)


s3_client = S3Client(
    bucket_name=DEFAULT_BUCKET,
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
)
s3_client.ensure_bucket(create_if_missing=True)

openai_client = OpenAIClient()
qa_llm = LLMAdapter(
    client=openai_client,
    model=QA_MODEL,
    temperature=QA_TEMPERATURE,
    system=QA_SYSTEM,
)
qa_agent = SlideQAAgent(llm=qa_llm)
OUTLINE_ARTIFACT_NAME = "presentation_outline.json"
SLIDE_DRAFT_ARTIFACT_NAME = "slide_draft.json"
INSIGHT_ARTIFACT_NAME = "insight_summary.json"
DECK_ARTIFACT_NAME = "presentation_deck.json"
WORKFLOW_ARTIFACT_NAME = "presentation_workflow.json"
LAYOUT_PLAN_ARTIFACT_NAME = "layout_plan.json"
QA_REPORTS_ARTIFACT_NAME = "qa_reports.json"
SLIDE_RENDER_ARTIFACT_NAME = "slide_render.png"
SLIDE_PACKAGE_ARTIFACT_NAME = "slide_package.json"

OUTLINE_SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    {
      "sections": [
        {
          "title": "string",
          "key_points": ["string", "..."],
          "suggested_visuals": ["string", "..."]
        }
      ],
      "slides": [
        {
          "slide_id": "S01",
          "beat": "string",
          "title": "Conclusion-led headline",
          "message": "Optional explanatory text or null",
          "expected_evidence": ["chart", "table"],
          "notes": "Optional execution notes or null"
        }
      ],
      "executive_summary": "Optional concise summary or null",
      "notes": "Optional planner notes or null"
    }
    """
).strip()

SLIDE_DRAFT_SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    {
      "slide": {
        "title": "string",
        "bullets": ["Point", "..."],
        "speaker_notes": "Optional footnote text or null",
        "suggested_visual": "Reference to artifact or null"
      },
      "rationale": "Why the slide looks this way",
      "needs_followup": true,
      "followup_hint": "Optional guidance for next slide or null",
      "ppt_artifact_path": "outputs/<filename>.pptx or null"
    }
    """
).strip()

DECK_SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    {
      "artifact_path": "s3://... or outputs/<file>",
      "preview_snippet": "Optional preview text or null",
      "slide_count": 5
    }
    """
).strip()

WORKFLOW_SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    {
      "thread_id": "string",
      "outline": <PresentationOutlineResponse>,
      "slide_drafts": {
        "S01": <SlideDraftResponse>,
        "S02": <SlideDraftResponse>
      },
      "deck": <PresentationAssemblyResponse or null>,
      "insights": {
        "S01": {"summary": "...", "artifacts": [...]}
      }
    }
    """
).strip()

LAYOUT_PLAN_SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    {
      "slide_id": "S07",
      "intent": "Narrative purpose for the slide",
      "layout_type": "title_chart_bullets",
      "theme": "Optional theme token",
      "regions": {
        "region_name": {"x":0.0,"y":0.0,"w":1.0,"h":0.2}
      },
      "callout_anchors": [
        {"id":"anchor_id","series":"metric_name","selector":"max"}
      ],
      "constraints": {
        "bullets_max": 3,
        "headline_max_chars": 90,
        "no_overlap": true
      }
    }
    """
).strip()

SLIDE_PACKAGE_SCHEMA_DESCRIPTION = textwrap.dedent(
    """
    {
      "insight": <InsightGenerationResponse>,
      "layout": <LayoutSpecification>,
      "draft": <SlideDraftResponse>,
      "qa_reports": [<SlideQAReport>, "..."],
      "render_artifact": {
        "name": "slide_render.png",
        "path": "outputs/slide_render.png or s3://...",
        "description": "Deterministic render of the slide",
        "artifact_type": "image"
      }
    }
    """
).strip()


@mcp.tool(
    name="plan_presentation_outline",
    description="Generate a high-level presentation outline for a given topic and audience. Reads from narrative artifacts. Produces a structured outline with sections and slides in JSON format. Artifacts should be text documents, reports, or data summaries relevant to the topic."
)
async def plan_presentation_outline(
    input: PresentationOutlineRequest, ctx: Context
) -> PresentationOutlineResponse:
    try:
        outline_planner = PresentationOutlinePlanner(
            llm=LLMAdapter(
                client=openai_client,
                model=os.getenv("OUTLINE_MODEL", "gpt-4.1-mini"),
                temperature=float(os.getenv("OUTLINE_TEMPERATURE", "0.1")),
                system="""
You are a world-class Presentation Generation Agent. Transform the provided narrative report and artifacts into a conclusion-led PowerPoint slide outline that tells a smooth, executive-ready story.

NON-NEGOTIABLES
- Stay strictly within the provided artifacts. Do NOT invent facts, vendors, or claims.
- One message per slide. Every title is an active-voice, result-oriented conclusion (no labels like “Introduction”).
- Output ONLY a single JSON object with a top-level key "slides", conforming EXACTLY to the provided schema (SlideOutline). No extra keys. No markdown. No code fences.

STORY FRAME (SCQA + Decision Flow)
- Organize the deck as a clear arc:
  1) Situation/Context: what matters now (hook + north star).
  2) Complication: the tension (where/when we miss or risk).
  3) Question: the decision we must make (what to fix first).
  4) Answer: insights that resolve the question (ranked, MECE).
  5) Implication: recommended actions with expected lift.
  6) Plan: 30/60/90 with owners, checkpoints, KPIs.
  7) Risks & mitigations (only the few that can derail the plan).
  8) Appendix: data quality, methods, backups. (Pull forward ONLY if they change conclusions.)

SLIDE CRAFT RULES
- Titles: write the takeaway, not the topic (e.g., “Market trends indicate a shift in consumer behavior”).
- Message: 1–2 crisp sentences that expand the claim (no fluff).
- expected_evidence: specify the minimal visuals that prove the claim (e.g., "Year×Product heatmap", "KPI callout", "Cause→Action table"). Prefer one decisive visual over many.
- Notes: write a short presenter transition (e.g., “This leads to the question of target calibration…”) and any execution guidance for chart binding (columns, grain, filters).
- Layout: suggest one of {Title only, Single chart, Single Chart + Bullets, Two column text, Image with caption}. Choose the simplest layout that proves the point.
- Keep a logical, audience-friendly order; each slide should naturally set up the next (use Notes for handoffs).
- If data quality issues exist, place them in Appendix unless they materially change the main claims; if they do, flag that on the first slide’s Notes.

EVIDENCE & RIGOR
- Prefer ranked, MECE insights; avoid overlap across slides.
- Quantify whenever the artifacts allow (absolute, % deltas, time windows).
- Do not repeat the same visual form unless it advances the story (e.g., sequence of variance → drilldown → driver).

BOUNDS & BUDGET
- Honor any slide-count hint; otherwise aim for a lean, executive deck. Merge or drop slides that do not advance the decision.

OUTPUT FORMAT (MANDATORY)
Return ONLY:
{
  "slides": [
    {
      "slide_id": "S01",
      "title": "...conclusion...",
      "message": "1–2 sentences expanding the claim.",
      "expected_evidence": ["..."],
      "notes": "Presenter transition + binding guidance.",
      "layout": "Single Chart + Bullets"
    }
    // S02…Sn
  ]
}

                """
            ),
            s3_client=s3_client,
            min_slides=int(os.getenv("OUTLINE_MIN_SLIDES", "5")),
            max_slides=int(os.getenv("OUTLINE_MAX_SLIDES", "20")),
            allowed_artifact_exts={".txt", ".md", ".json", ".csv", ".tsv", ".xlsx", ".pdf"},
        )
        outline = outline_planner.plan_outline(input)
        await ctx.info(
            f"Prepared a presentation outline with {len(outline.slides)} slides."
        )
        return outline
    except Exception as exc:
        await ctx.error(f"Failed to plan presentation outline: {exc}")
        raise



@mcp.tool(
    name="generate_slide",
    description=(
        "Produce a fully formatted slide by combining quantitative insights, layout planning, deterministic rendering, "
        "and QA-driven refinements into a single pipeline."
        "Uses code agent for insight generation, layout planning, and slide remediation."
        "Reads from staged data assets and artifacts, writes to outputs/ in local or S3 storage."
    ),
)
async def generate_slide(
    input: GenerateSlideRequest, 
    ctx: Context
) -> dict:
    try:
        thread_id = input.thread_id
        insight_req: InsightGenerationRequest = input.insight
        slide_outline = input.slide_outline
        # draft_req: SlideDraftRequest = input.draft

        # draft_request_payload = draft_req.model_dump()

        ppt_basename = slide_outline.slide_id
        ppt_basename = (ppt_basename or "slide").strip().replace(" ", "_")
        ppt_filename = f"{ppt_basename}.pptx"
        ppt_relative_path = f"outputs/{ppt_filename}"

        artifact_index: Dict[str, str] = {}

        # ------------------------------------------------------------------ #
        # Stage 1: Quantitative insights
        # ------------------------------------------------------------------ #
        # Retrieve the research docs from the insights payload
        insights_reference = insight_req.research_context or []
        research_context = ""
        data_assets_info = ""

        for research in insights_reference:
            research_data, _ = s3_client.get_bytes(key=research.path)
            research_txt = research_data.decode("utf-8")
            if research_txt:
                research_context += f"\n- **{research.name}**\n{research_txt}"
                
        data_assets = insight_req.data_assets or []
        
        for data_asset in data_assets:
            data_assets_info += f"\n- **{data_asset.name}**\n  Path: {data_asset.path}\n"
            if data_asset.description:
                data_assets_info += f"  Description: {data_asset.description}\n"
            if data_asset.size is not None:
                data_assets_info += f"  Size: {data_asset.size}\n"

        insight_prompt = textwrap.dedent(
            f"""
You are the quantitative insights agent for ArrowAI.

Research context:
{research_context}

Task:
{insight_req.task}

Artifacts:
{data_assets_info}

Requirements:
1. Analyse the staged datasets to compute statistically sound metrics, tables, and charts that support the slide narrative.
2. Save the structured summary to 'outputs/{INSIGHT_ARTIFACT_NAME}'
3. Do NOT create layout plans, PPTX files, or slide renders in this step.
4. Charts/Graphs must have:
    - transparent background
    - at least 800px wide keep the aspect ratio reasonable, with ample margins
    - Prioritize dark text on light background.
    - No title as the slide title will be used.
"""
        )
        
        log.info(f"Submitting prompt for insight generation {insight_prompt}.")

        insight_response_raw = await call_code_agent(
            task=insight_prompt,
            thread_id=thread_id,
            data_assets=insight_req.data_assets,
            timeout=CODE_AGENT_TIMEOUT,
            max_steps=CODE_AGENT_MAX_STEPS,
            repair_attempts=2,
        )
    
        log.info(f"Insight generation completed for thread {thread_id}.")

        insight_response = json.loads(insight_response_raw)
        
        # Unpack the insight response to return
        insights_artifacts = "Artifacts produced from analysis:\n"
        
        # Get the files out
        files_out = insight_response.get("files_out") or []
        
        log.info(f"Insight files out: {files_out}")
        
        insight_summary = ''
        
        for file in files_out:
            file = json.loads(file) if isinstance(file, str) else file
            if file.get("name") != INSIGHT_ARTIFACT_NAME:
                # This will be the images, tables, etc
                insights_artifacts += f"\n- **{file.get('name', 'unknown')}**\n  Path: {file.get('path', 'unknown')}\n"
            else:
                # Read the json from s3 
                insight_summary = _read_artifact(file.get("path", ""))
                
        _append_slide_log(thread_id, f"### Insight Summary\n\n```json\n{insight_summary}\n```\n", slide_outline.slide_id)
                
        # ------------------------------------------------------------------ #
        # Stage 2: Layout planning + initial render
        # ------------------------------------------------------------------ #
        layout_prompt = textwrap.dedent(
            f"""
You are the layout planning and rendering agent for ArrowAI.

Slide outline (from previous step):
{slide_outline.model_dump()}

Insight summary (from previous step):
{insight_summary}

Insight artifacts:
{insights_artifacts}

Tasks:
1. Produce a layout specification saved to 'outputs/{LAYOUT_PLAN_ARTIFACT_NAME}' following:
    {LAYOUT_PLAN_SCHEMA_DESCRIPTION}
2. Build an initial slide in PPTX format at '{ppt_relative_path}', embedding charts/tables generated earlier where appropriate, include key insights and labels if there is a chart as text boxes.
3. Do NOT run QA fixes in this step. Finish with 'DONE'.
            """
        )
        
        log.info(f"Submitting prompt for layout generation {layout_prompt}.")
        
        layout_response = await call_code_agent(
            task=layout_prompt,
            thread_id=thread_id,
            timeout=240,
            max_steps=max(4, CODE_AGENT_MAX_STEPS),
            repair_attempts=1,
        )
        
        layout_response = json.loads(layout_response)

        log.info(f"Layout files out: {layout_response.get('files_out', [])}")

        layout_spec = _load_json_artifact(layout_response, LAYOUT_PLAN_ARTIFACT_NAME)
        
        _append_slide_log(thread_id, f"### Layout Specification\n\n```json\n{_json_dump(layout_spec)}\n```\n", slide_outline.slide_id)
        
        slide_render_path = _find_artifact_path(layout_response, ppt_filename)
        slide_render_pptx = _read_artifact(slide_render_path)

        artifact_responses: List[Dict[str, Any]] = [insight_response, layout_response]
        current_layout = layout_spec
        qa_reports: List[SlideQAReport] = []
        
        # ------------------------------------------------------------------ #
        # Stage 3: QA loop with in-process QA agent
        # ------------------------------------------------------------------ #
        # for cycle in range(1, input.max_qa_cycles + 1):
        for cycle in range(1, 4):
            
            slide_render_path = _find_artifact_path(artifact_responses[-1], ppt_filename)
            slide_render_pptx = _read_artifact(slide_render_path)

            qa_report = qa_agent.evaluate(
                slide=slide_render_pptx,
                layout=current_layout,
                slide_outline=slide_outline.model_dump(),
                insight_summary=insight_summary,
                qa_report=qa_reports[-1] if qa_reports else None,
                cycle=cycle,
                max_cycles=3,
            )
            qa_reports.append(qa_report)
            log.info(
                f"QA cycle {cycle} for thread {thread_id} status: {qa_report.status}"
            )
            
            _append_slide_log(thread_id, f"### QA Report Cycle {cycle}\n\n```json\n{_json_dump(qa_report.model_dump())}\n```\n", slide_outline.slide_id)

            if qa_report.status == "PASS":
                # Download the Latest PPTX path
                log.info(f"Slide passed QA in cycle {cycle} for thread {thread_id}.")
                slide_render_path = _find_artifact_path(artifact_responses[-1], ppt_filename)
                s3_client.download_file(slide_render_path, os.path.join(TMP_DIR, thread_id, ppt_filename))
                break

            qa_report_dict = qa_report.model_dump()
            
            log.info(f"QA report dict: {qa_report_dict}")
            
            history = [report.model_dump() for report in qa_reports]

            fix_prompt = textwrap.dedent(
                f"""
You are the slide remediation agent for ArrowAI.

Inputs:
- Slide Outline: {_json_dump(slide_outline.model_dump())}
- Insight summary: {_json_dump(insight_summary)}
- Previous layout specification: {_json_dump(current_layout)}
- All QA reports so far: {_json_dump(history)}
- PPTX path: '{ppt_relative_path}'

Objectives:
1. Update the layout specification and PPTX to resolve all QA issues, applying patch guidance exactly.
2. Refresh 'outputs/{LAYOUT_PLAN_ARTIFACT_NAME}' to reflect the updated layout (schema above).
3. Persist the cumulative QA history to 'outputs/{QA_REPORTS_ARTIFACT_NAME}' so it can be referenced in future QA cycles.
4. Emit ARTIFACT lines for every file touched and finish with 'DONE'.
5. Return {ppt_filename} and {LAYOUT_PLAN_ARTIFACT_NAME} as Artifacts.
                """
            )
            
            log.info(f"Submitting prompt for slide fix {fix_prompt}.")

            fix_response = await call_code_agent(
                tool_name="code_orchestrate",
                task=fix_prompt,
                thread_id=thread_id,
                timeout=300,
                max_steps=max(6, CODE_AGENT_MAX_STEPS),
                repair_attempts=1,
            )
            
            fix_response = json.loads(fix_response)
            
            log.info(f"fix_response files out: {fix_response.get('files_out', [])}")

            artifact_responses.append(fix_response)

            try:
                current_layout = _load_json_artifact(fix_response, LAYOUT_PLAN_ARTIFACT_NAME)
                _append_slide_log(thread_id, f"### Updated Layout Specification\n\n```json\n{_json_dump(current_layout)}\n```\n", slide_outline.slide_id)
            except ValueError:
                layout_path = artifact_index.get(LAYOUT_PLAN_ARTIFACT_NAME)
                if not layout_path:
                    raise
                current_layout = _load_json_from_path(layout_path)
        
        else:
            log.info(f"Max QA cycles reached for thread {thread_id}.")

        _append_slide_log(thread_id, f"### Slide Generation Complete\n\nFinal slide PPTX at\n- **Local**: '{TMP_DIR}/{thread_id}/{ppt_filename}'\n- **S3**: '{slide_render_path}'\n", slide_outline.slide_id)
        return {
            "layout": current_layout,
            "insights": insight_summary,
            "final_qa_report": qa_reports[-1],
            "ppt_artifact_path": f"{TMP_DIR}/{thread_id}/{ppt_filename}",
        }
    except Exception as exc:
        log.error(f"Error during slide generation: {exc}")
        await ctx.error(f"Failed to generate slide: {exc}")
        raise

@mcp.tool(
    name="assemble_presentation",
    description=(
        "Reads all previously drafted slides from the run directory, combines them into a single PowerPoint presentation deck, uploads the final deck to S3, and returns the artifact details."
    )
)
async def assemble_presentation(
    input: PresentationAssemblyRequest, ctx: Context
) -> dict:
    thread_id = input.thread_id
    try:
        # Read the all slides in the _run_dir
        slide_files = []
        run_dir = _run_dir(thread_id)
        if not run_dir.exists() or not run_dir.is_dir():
            await ctx.error(f"Run directory '{run_dir}' does not exist or is not a directory.")
            raise RuntimeError(f"Run directory '{run_dir}' does not exist or is not a directory.")
        
        for item in run_dir.iterdir():
            if item.is_file() and item.name.endswith(".pptx"):
                slide_files.append(item)

        for slide_file in slide_files:
            log.info(f"Found slide file: {slide_file}")
        if not slide_files:
            await ctx.error(f"No slide files found in run directory '{run_dir}'.")
            raise RuntimeError(f"No slide files found in run directory '{run_dir}'.")
                
        output_name = (input.title or f"{thread_id}_final_deck.pptx").rstrip(".pptx") + ".pptx"
        out_path, count = assemble_pptx_from_directory(_run_dir(thread_id), _presentation_dir(thread_id), output_name)

        s3_key = f"outputs/{output_name}"
        artifact_info = s3_client.put_file(str(out_path), s3_key)
        s3_artifact_path = artifact_info.uri
        s3_artifact_size = artifact_info.size

        log.info(f"Final presentation assembled at {out_path} and uploaded to {s3_artifact_path}.")
        return {
            "name": output_name,
            "path": s3_artifact_path,
            "slide_count": count,
            "size": s3_artifact_size,
        }
    except Exception as exc:
        await ctx.error(f"Failed to assemble presentation: {exc}")
        raise
    
    
    
    

# @mcp.tool(name="ping", description="Health check for the presentation MCP server.")
# def ping() -> Dict[str, str]:
#     return {"status": "ok"}


# @mcp.tool()
# async def check_code_agent() -> Dict[str, str]:
#     try:
#         await _ensure_tools_loaded()
#         log.info("Pinging code agent via MCP client...")
#         ping_response = await call_code_agent(
#             task=textwrap.dedent(
#                 """
#                 Create a trivial heartbeat artifact for the presentation agent.
#                 Steps:
#                 - Write the text 'presentation-agent: pong' to outputs/ping.txt.
#                 - Log the artifact and finish with DONE.
#                 """
#             ),
#             thread_id=f"ping-{uuid4().hex[:8]}",
#             timeout=90,
#             max_steps=1,
#         )
#         return {
#             "status": "code agent reachable",
#             "response": json.dumps(ping_response, ensure_ascii=False),
#         }
#     except Exception as exc:
#         log.error("Failed to initialise MCP client for code agent: %s", exc)
#         return {"status": "code agent unreachable"}

def main(argv: Optional[List[str]] = None) -> None:
    log.info(
        "Starting Presentation MCP server on %s:%s (path=%s)",
        HOST,
        PORT,
        PATH,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
