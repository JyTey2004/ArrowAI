# mcp/research_agent/main.py
from __future__ import annotations

import pathlib
import time
import os
import logging, sys
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP, Context

from services.openai_client import OpenAIClient
from services.perplexity_client import PerplexityClient
from aws.s3_client import S3Client

from utils.LLMAdapter import LLMAdapter

from components.models import ResearchRequest
from components.analyzer import Analyzer
from components.research import Research 

# ---------- MCP bootstrap ----------
s3c = S3Client(
    bucket_name=os.environ.get("MCP_BUCKET", "arrowai"),
    region_name=os.environ.get("AWS_REGION", "ap-southeast-1"),
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
)

host = os.getenv("RESEARCH_HOST", "127.0.0.1")
port = int(os.getenv("RESEARCH_PORT", "5001"))
path = os.getenv("RESEARCH_PATH", "/mcp/research_agent")
mcp = FastMCP("ResearchSubAgent", port=port, host=host, streamable_http_path=path)
analyzer = Analyzer(s3_client=s3c, base_tmp_dir="tmp")  # all I/O stays under tmp/
researcher = Research(s3_client=s3c, base_tmp_dir="tmp")  # all I/O stays under tmp/

def _setup_logging():
    level = os.getenv("RESEARCH_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.INFO)

_setup_logging()
log = logging.getLogger("research-agent")

# ---------- dirs ----------
def _run_dir(thread_id: str) -> pathlib.Path:
    return analyzer._research_dir(thread_id).resolve()

def _inputs_dir(thread_id: str) -> pathlib.Path:
    """Absolute path to run_dir/inputs for this thread."""
    rd = _run_dir(thread_id)
    d = rd / analyzer.inputs_dirname
    d.mkdir(parents=True, exist_ok=True)
    return d

# ---------- clients ----------
oai = OpenAIClient()           # analyze_llm
perplexity = PerplexityClient()  # search_llm


# ---------- LLM adapters ----------
ARTIFACT_SYSTEM = (
    "You are a senior researcher, find out all information in the file below relevant to the user's goal"
    "Be as specific and detailed as possible, extract all relevant information. Be specific about numbers, dates, names, places, and any other relevant details."
    "If data contains tables, trends, or patterns, describe them in detail."
)

ANALYZE_SYSTEM = (
  "You are a senior research planner.\n"
  "Input: RESEARCH_LOG (user goal plus any per-artifact findings).\n"
  "Task: Produce a SEARCH PLAN in strict JSON to guide evidence gathering.\n"
  "\n"
  "CONSTRAINTS:\n"
  "- Max 5 non-overlapping sub_topics; include only what is relevant to the RESEARCH_LOG.\n"
  "- You should start with searches to gather initial information, then follow up with analyses to deepen understanding.\n"
  "- Sub topics must be in a logical order (e.g., foundational concepts before advanced topics, chronological order if applicable).\n"
  "- Search will be to find external information (e.g., recent developments, statistics, case studies).\n"
  "- Analysis will be reading/understanding/summarizing artifacts/search results. You have no tools other than a browser.\n"
  "- Each sub_topic has 1-5 questions on ask questions that are specific and relevant to the sub_topic.\n"
  "- Questions must be specific, executable, and phrased so they can be used directly as search queries or analysis tasks.\n"
  "- Keep strings concise and single-line (no line breaks inside values).\n"
  "- Prefer measurable, verifiable language (e.g., baseline, variability, trend change, seasonality/cycles if applicable, outliers, data completeness, external context) over vague terms like 'typical' or 'general overview'.\n"
  "- Prioritize internal validation (definitions, baselines) before external benchmarking or context.\n"
  "- Questions must be phrased to yield factual, evidence-backed answers.\n"
  "- Deduplicate: no overlapping titles or repeated questions.\n"
  "\n"
  "OUTPUT FORMAT (return ONLY this JSON object—no markdown, fences, or commentary):\n"
  "{\n"
  "  \"sub_topics\": [\n"
  "    {\n"
  "      \"title\": \"string (short, specific)\",\n"
  "      \"action\": \"string (one of: 'search', 'analysis')\",\n"
  "      \"rationale\": \"string (1–2 lines referencing findings/gaps in RESEARCH_LOG)\",\n"
  "      \"questions\": [string, ...],  # list of 1–5 specific questions to answer\n"
  "      \"country\": \"string (optional, ISO country code to tailor search results)\"\n"
  "    }\n"
  "\n"
)

ANALYSIS_SYSTEM = (
    "You are a senior researcher, analyze the following file in detail to extract all relevant information.\n"
    "- RESEARCH_LOG.md contains user queries and artifacts."
    "- SEARCH_LOG.md contains search results."
    "Answer the list of questions below based on the information in RESEARCH_LOG.md and SEARCH_LOG.md."
)

SUMMARY_SYSTEM = (
    "You are a senior researcher reporting to the main agent.\n"
    "Summarize WHAT WAS DONE and WHAT WAS LEARNED so the planner can decide next steps.\n"
    "Output MUST be valid JSON matching the provided schema. No markdown, no comments.\n"
    "\n"
    "Instructions:\n"
    "- Be concise and decision-oriented; write for a domain-savvy colleague.\n"
    "- key_findings should be factual and, where possible, traceable to sources. Use bullet points and numbered lists for clarity.\n"
    "- gaps capture unknowns or missing evidence with impact and suggested unblocker.\n"
    "- artifacts are files provided as input or found during research, return relevant file paths and fill in the description.\n"
    "- If unsure, leave fields empty rather than hallucinating.\n"
)

artifact_llm = LLMAdapter(
    client=oai,
    model="gpt-4.1-mini",
    temperature=0,
    system=ARTIFACT_SYSTEM
)

analyze_llm = LLMAdapter(
    client=oai,
    model="gpt-4.1-mini",
    temperature=0,
    system=ANALYZE_SYSTEM
)

analysis_llm = LLMAdapter(
    client=oai,
    model="gpt-4.1-mini",
    temperature=0,
    system=ANALYSIS_SYSTEM
)

summary_llm = LLMAdapter(
    client=oai,
    model="gpt-4.1-mini",
    temperature=0,
    system=SUMMARY_SYSTEM
)

# ---------- MCP tool ----------
@mcp.tool(
    name="analyze_and_research",
    description=(
        "Stateful research agent that takes a task and iteratively researches and refines a plan to achieve it. "
        "Do not pass in big unprocessed artifacts, this tool cannot handle data processing."
        "Instead, pass in artifacts like reports/summaries/logs that have been pre-processed. "
        "Uses artifacts stored on S3 as needed; returns a research_report.md with sources."
    ),
)
async def analyze_and_research(
    input: ResearchRequest,
    ctx: Context,
) -> Dict[str, Any]:
    """
    input: {
        "task": "user goal / topic",
        "thread_id": "unique ID for this research thread",
        "files_in": [  # files already available (e.g. downloaded from S3)
            {
            "name": "file name",
            "path": "full path of the file e.g s3://bucket/key",
            "size": 12345,  # optional
            }
        ]   
    """
    task = input.task or ""
    # await ctx.info(f"Research task received for thread_id={input.thread_id!r}")
    
    try:
        
        # ------ Seed RESEARCH_LOG ------
        header = f"# Research Log: \n\n## User Query:\n{task}\n"
        
        analyzer._append_research_log(input.thread_id, header)

        # ------ Analyze the Artifacts ------
        analysis_results = await analyzer.analyze(input.thread_id, task, input.files_in, artifact_llm, analyze_llm)

        # ------ Research ------
        report_summary = await researcher.research(input.thread_id, task, analysis_results, perplexity, analysis_llm, summary_llm, upload_to_s3=True)
        
        return {
            "Key Findings": report_summary.key_findings,
            "Gaps": report_summary.gaps,
            "Artifacts": [a.model_dump() for a in report_summary.artifacts],
        }

    except Exception as e:
        log.error(f"Error in analyze_and_research: {e}")
        await ctx.error(f"Error in analyze_and_research: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    log.info("Starting Research MCP (HTTP) …")
    mcp.run(transport="streamable-http")
