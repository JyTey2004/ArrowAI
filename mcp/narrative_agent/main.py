# mcp/narrative_agent/main.py
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from components import NarrativeComposer, NarrativeOutput, NarrativeRequest
from aws.s3_client import S3Client
from services.openai_client import OpenAIClient
from utils.LLMAdapter import LLMAdapter

load_dotenv()


def _setup_logging() -> None:
    level = os.getenv("NARRATIVE_LOG_LEVEL", "INFO").upper()
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
log = logging.getLogger("narrative-agent")

# ---------- Configuration ----------
DEFAULT_BUCKET = os.environ.get("MCP_BUCKET", "arrowai")
REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
HOST = os.environ.get("NARRATIVE_HOST", "127.0.0.1")
PORT = int(os.environ.get("NARRATIVE_PORT", "5003"))
PATH = os.environ.get("NARRATIVE_PATH", "/mcp/narrative_agent")
TMP_DIR = os.environ.get("NARRATIVE_TMP_DIR", "tmp")
UPLOAD_TO_S3 = os.environ.get("NARRATIVE_UPLOAD_TO_S3", "true").lower() != "false"

NARRATIVE_MODEL = os.environ.get("NARRATIVE_MODEL", os.environ.get("SANDBOX_ARTIFACT_MODEL", "gpt-4.1-mini"))
NARRATIVE_TEMPERATURE = float(os.environ.get("NARRATIVE_TEMPERATURE", "0.4"))

NARRATIVE_SYSTEM = (
    "You are a principal consultant crafting board-ready narratives.\n"
    "Blend quantitative insight with executive storytelling, cite artifacts explicitly, and focus on actionable recommendations."
)

ARTIFACT_MODEL = os.environ.get("NARRATIVE_ARTIFACT_MODEL", NARRATIVE_MODEL)
ARTIFACT_TEMPERATURE = float(os.environ.get("NARRATIVE_ARTIFACT_TEMPERATURE", "0.1"))
ARTIFACT_SYSTEM = (
    "You are an insights analyst. Given an artifact, extract every detail that would be useful for crafting a business narrative. "
    "List KPIs, trends, benchmarks, stakeholders, risks, opportunities, and recommendations. Be concise but comprehensive."
)

# ---------- Clients ----------
s3_client = S3Client(
    bucket_name=DEFAULT_BUCKET,
    region_name=REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
)

openai_client = OpenAIClient()

composer = NarrativeComposer(
    s3_client=s3_client,
    artifact_llm=LLMAdapter(
        client=openai_client,
        model=ARTIFACT_MODEL,
        temperature=ARTIFACT_TEMPERATURE,
        system=ARTIFACT_SYSTEM,
    ),
    base_tmp_dir=TMP_DIR,
)
narrative_llm = LLMAdapter(
    client=openai_client,
    model=NARRATIVE_MODEL,
    temperature=NARRATIVE_TEMPERATURE,
    system=NARRATIVE_SYSTEM,
)

mcp = FastMCP(
    "NarrativeAgent",
    host=HOST,
    port=PORT,
    streamable_http_path=PATH,
)


def _serialise_output(result: NarrativeOutput) -> Dict[str, Any]:
    return {
        "narrative_md": result.narrative_md,
        "executive_summary_md": result.executive_summary_md,
        "talking_points_md": result.talking_points_md,
        "artifacts": [artifact.model_dump() for artifact in result.artifacts],
    }


@mcp.tool(
    name="compose_narrative",
    description=(
        "Compose a business-ready narrative and executive summary from provided artifacts. "
        "Input must include the user goal, thread_id, and available artifact metadata."
    ),
)
async def compose_narrative(
    input: NarrativeRequest,
    ctx: Context,
) -> Dict[str, Any]:
    try:
        log.info(
            "Narrative request received (thread_id=%s, artifacts=%s)",
            input.thread_id,
            len(input.files_in),
        )
        await ctx.info(
            f"[narrative] Generating storyline for thread {input.thread_id} with {len(input.files_in)} artifact(s)."
        )

        output = composer.compose(
            thread_id=input.thread_id,
            request=input,
            narrative_llm=narrative_llm,
            upload_to_s3=UPLOAD_TO_S3,
        )

        await ctx.info("[narrative] Narrative generation complete.")
        return _serialise_output(output)
    except Exception as exc:
        log.exception("Narrative generation failed: %s", exc)
        await ctx.error(f"Narrative generation failed: {exc}")
        return {"error": str(exc)}


@mcp.tool(name="ping", description="Health check for the narrative agent.")
def ping() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    log.info("Starting Narrative MCP (HTTP)…")
    mcp.run(transport="streamable-http")
