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
    "Input: USER_GOAL, RESEARCH_LOG (Previous Research) and ARTIFACTS_LOG (File Insights).\n"
    "Task: Propose the next three research questions that will unlock the goal.\n"
    "\n"
    "Constraints:\n"
    "- Output must be strict JSON with keys: 'rationale' (string) and 'questions' (array of exactly 3 strings).\n"
    "- Questions must be specific, answerable with web research, and mutually complementary (no duplicates).\n"
    "- Each question should reflect evidence gaps surfaced in RESEARCH_LOG and move the investigation forward.\n"
    "- Keep values single-line (no embedded newlines).\n"
    "- If context is insufficient, still propose well-structured exploratory questions.\n"
    "\n"
    "Example output (do NOT include comments):\n"
    "{\"rationale\": \"Why these questions matter...\", \"questions\": [\"Question 1\", \"Question 2\", \"Question 3\"]}"
)

ANALYSIS_SYSTEM = (
    "You are the research synthesizer for an iterative investigation.\n"
    "Input provides USER_GOAL, the cumulative SEARCH_LOG, and prior ANALYSIS summaries and ARTIFACTS_LOG.\n"
    "Task: produce a refreshed synthesis for the current loop, decide whether the goal is answered, and surface up to three next questions.\n"
    "\n"
    "Output must be STRICT JSON with keys: \n"
    "- summary: markdown bullet points and short paragraphs capturing findings from ALL iterations so far, highlighting what is new this round. Include links to search results where applicable. TThis should never be empty.\n"
    "- next_questions: array of up to three forward-looking questions (omit or empty array if goal is satisfied).\n"
    "- task_answered: boolean indicating if the user's goal is sufficiently answered.\n"
    "Do not include commentary outside the JSON. Do not include code fencing.\n"
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
        "Stateful research agent that takes a task and iteratively researches and refines a plan to achieve it."
        "Do not pass in big unprocessed artifacts, this tool cannot handle data processing."
        "Instead, pass in artifacts like reports/summaries/logs that have been pre-processed. "
        "Uses artifacts stored on S3 as needed;"
        "Returns key findings, gaps, and any new artifacts generated."
        "A research report will be in the artifacts."
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
        initial_plan = await analyzer.analyze(input.thread_id, task, input.files_in, artifact_llm, analyze_llm)

        # Log derived questions for observability
        log.info(
            "Initial research questions for thread %s: %s",
            input.thread_id,
            "; ".join(initial_plan.questions),
        )

        # ------ Research ------
        report_summary = await researcher.research(
            input.thread_id,
            task,
            initial_plan,
            perplexity,
            analysis_llm,
            summary_llm,
            upload_to_s3=True,
        )
        
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
