# mcp/artifact_agent/main.py
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP, Context

from aws.s3_client import S3Client
from components import ArtifactReader, ArtifactLogManager
from components.models import (
    ArtifactFetchRequest,
    ArtifactTextResponse,
    UnderstandFileRequest,
    UnderstandFileResponse,
)
from components.log_manager import IMAGE_FILE_TYPES, RICH_FILE_TYPES, TEXT_FILE_TYPES
from services.openai_client import OpenAIClient
from utils.LLMAdapter import LLMAdapter


def _setup_logging() -> None:
    level = os.getenv("ARTIFACT_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.INFO)


_setup_logging()
log = logging.getLogger("artifact-mcp")

# --- Configuration ---
DEFAULT_BUCKET = os.environ.get("MCP_BUCKET", "arrowai")
REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
HOST = os.environ.get("ARTIFACT_HOST", "127.0.0.1")
PORT = int(os.environ.get("ARTIFACT_PORT", "5002"))
PATH = os.environ.get("ARTIFACT_PATH", "/mcp/artifacts")

DEFAULT_MAX_BYTES = int(os.environ.get("ARTIFACT_DEFAULT_MAX_BYTES", "32000"))
HARD_MAX_BYTES = int(os.environ.get("ARTIFACT_HARD_MAX_BYTES", "200000"))
PRESIGN_TTL = int(os.environ.get("ARTIFACT_PRESIGN_TTL", "3600"))
MAX_INLINE_BYTES = int(os.environ.get("ARTIFACT_MAX_INLINE_BYTES", "64000"))

SUMMARY_MODEL = os.environ.get("ARTIFACT_SUMMARY_MODEL", os.environ.get("SANDBOX_ARTIFACT_MODEL", "gpt-4.1-mini"))
SUMMARY_TEMPERATURE = float(os.environ.get("ARTIFACT_SUMMARY_TEMPERATURE", "0.0"))

ARTIFACT_TMP_DIR = os.environ.get("ARTIFACT_TMP_DIR", "tmp")

ARTIFACT_SYSTEM = (
    "You are a data scientist. Read the provided artifact and extract every detail that is useful for the user's goal.\n"
    "Respond as a markdown bullet list (no surrounding quotes). Include:\n"
    "- File name and path (if available)\n"
    "- Key facts, numbers, dates, stakeholders, metrics\n"
    "- Column names with short descriptions when data tables are present\n"
    "- Any evident trends, anomalies, or caveats\n"
    "Be precise and factual. Do not fabricate information. Keep bullets concise but information-dense."
)

# --- Clients ---
s3_client = S3Client(
    bucket_name=DEFAULT_BUCKET,
    region_name=REGION,
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
)

artifact_reader = ArtifactReader(
    s3_client=s3_client,
    default_max_bytes=DEFAULT_MAX_BYTES,
    hard_max_bytes=HARD_MAX_BYTES,
    presign_ttl=PRESIGN_TTL,
)

mcp = FastMCP(
    "ArtifactService",
    port=PORT,
    host=HOST,
    streamable_http_path=PATH,
)

openai_client = OpenAIClient()
artifact_llm = LLMAdapter(
    client=openai_client,
    model=SUMMARY_MODEL,
    temperature=SUMMARY_TEMPERATURE,
    system=ARTIFACT_SYSTEM,
)

artifact_log_manager = ArtifactLogManager(
    reader=artifact_reader,
    s3_client=s3_client,
    summary_llm=artifact_llm,
    base_tmp_dir=ARTIFACT_TMP_DIR,
    presign_ttl=PRESIGN_TTL,
    max_inline_bytes=MAX_INLINE_BYTES,
)


@mcp.tool(
    name="fetch_artifact_text",
    description="Fetch textual content (with optional truncation) for an artifact stored in S3. "
    "Provide an s3:// URI or key; binary files return a presigned URL instead of text.",
)
async def fetch_artifact_text(input: ArtifactFetchRequest, ctx: Context) -> ArtifactTextResponse:
    log.info("Artifact fetch requested for path=%s name=%s", input.path, input.name or "<auto>")
    try:
        result_dict: dict[str, Any] = artifact_reader.fetch_text(
            path=input.path,
            name=input.name,
            max_bytes=input.max_bytes,
            encoding=input.encoding,
            include_presigned_url=input.include_presigned_url,
        )
        response = ArtifactTextResponse.model_validate(result_dict)
        await ctx.info(
            f"[artifact] fetched {response.name} "
            f"(size={response.size}, truncated={response.truncated}, binary={response.binary})"
        )
        return response
    except Exception as exc:
        log.exception("Failed to fetch artifact from %s", input.path)
        await ctx.error(f"Artifact fetch failed: {exc}")
        raise


@mcp.tool(name="ping", description="Health check for the artifact MCP server.")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@mcp.tool(
    name="understand_file",
    description=(
        "Append artifact insights to the thread's ARTIFACTS.md log. "
        "If the artifact is large, returns a message indicating the coding agent should process it instead."
    ),
)
async def understand_file(input: UnderstandFileRequest, ctx: Context) -> UnderstandFileResponse:
    artifact = input.artifact
    head = s3_client.head_object(artifact.path)
    size = artifact.size or head.get("ContentLength", 0)
    artifact_type = ArtifactLogManager.guess_file_type(artifact.name)
    log_path = str(artifact_log_manager.artifacts_log_path(input.thread_id))

    if artifact_log_manager.already_logged(input.thread_id, artifact.name):
        message = f"Artifact {artifact.name} already logged; skipping duplicate summary."
        await ctx.info(message)
        return UnderstandFileResponse(
            status="duplicate",
            message=message,
            log_path=log_path,
            artifact_size=size,
            artifact_type=artifact_type,
        )

    max_bytes = min(input.max_bytes or MAX_INLINE_BYTES, artifact_log_manager.max_inline_bytes)

    if size and size > max_bytes:
        entry, reason = artifact_log_manager.log_skip(
            input.thread_id,
            artifact,
            f"file too large ({size} bytes > {max_bytes})",
        )
        message = (
            f"{artifact.name} is {size} bytes which exceeds the inline processing limit. "
            "Please ask the coding agent to process this artifact."
        )
        await ctx.info(f"[artifact] {message}")
        return UnderstandFileResponse(
            status="too_large",
            message=message,
            log_entry=entry,
            log_path=log_path,
            artifact_size=size,
            artifact_type=artifact_type,
        )

    try:
        if artifact_type in (RICH_FILE_TYPES | IMAGE_FILE_TYPES):
            entry, summary, url = artifact_log_manager.summarize_rich_artifact(
                thread_id=input.thread_id,
                user_goal=input.user_goal,
                artifact=artifact,
                file_type=artifact_type,
            )
            await ctx.info(f"Logged rich artifact {artifact.name}")
            return UnderstandFileResponse(
                status="logged",
                summary=summary,
                log_entry=entry,
                log_path=log_path,
                artifact_size=size,
                artifact_type=artifact_type,
                presigned_url=url,
            )
        elif artifact_type in TEXT_FILE_TYPES:
            entry, summary, truncated, url = artifact_log_manager.summarize_text_artifact(
                thread_id=input.thread_id,
                user_goal=input.user_goal,
                artifact=artifact,
                max_bytes=max_bytes,
            )
            await ctx.info(f"Logged text artifact {artifact.name}")
            return UnderstandFileResponse(
                status="logged",
                summary=summary,
                log_entry=entry,
                log_path=log_path,
                artifact_size=size,
                artifact_type=artifact_type,
                presigned_url=url,
                truncated=truncated,
            )
        else:
            entry, reason = artifact_log_manager.log_skip(
                input.thread_id,
                artifact,
                f"unsupported file type ({artifact_type})",
            )
            message = f"Unsupported artifact type '{artifact_type}' for {artifact.name}. Use coding agent if needed."
            await ctx.info(f"[artifact] {message}")
            return UnderstandFileResponse(
                status="unsupported",
                message=message,
                log_entry=entry,
                log_path=log_path,
                artifact_size=size,
                artifact_type=artifact_type,
            )
    except Exception as exc:
        log.exception("Failed to understand artifact %s", artifact.name)
        await ctx.error(f"Failed to understand artifact: {exc}")
        raise


if __name__ == "__main__":
    log.info(
        "Starting Artifact MCP server on %s:%s (path=%s, bucket=%s)",
        HOST,
        PORT,
        PATH,
        DEFAULT_BUCKET,
    )
    mcp.run(transport="streamable-http")
