from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ArtifactFetchRequest(BaseModel):
    """Input payload for fetching artifact text from S3."""

    path: str = Field(..., description="S3 URI or S3 key pointing to the artifact.")
    name: Optional[str] = Field(
        default=None,
        description="Optional friendly name; defaults to the basename inferred from the path.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description; unused by the server but kept for parity with other models.",
    )
    max_bytes: Optional[int] = Field(
        default=None,
        ge=1024,
        le=500_000,
        description="Maximum number of bytes to fetch from the artifact (defaults to server setting).",
    )
    encoding: Optional[str] = Field(
        default=None,
        description="Preferred text encoding. If omitted the server infers it from headers or tries UTF-8.",
    )
    include_presigned_url: bool = Field(
        default=True,
        description="Whether to include a presigned download URL in the response.",
    )


class ArtifactTextResponse(BaseModel):
    name: str
    path: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    encoding: Optional[str] = None
    text: Optional[str] = None
    truncated: bool = False
    decode_errors: bool = False
    presigned_url: Optional[str] = None
    etag: Optional[str] = None
    version_id: Optional[str] = Field(default=None, alias="versionId")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    binary: bool = False
    message: Optional[str] = None

    class Config:
        populate_by_name = True


class ArtifactSpec(BaseModel):
    name: str
    path: str = Field(..., description="S3 URI or key for the artifact.")
    description: Optional[str] = None
    size: Optional[int] = None


class UnderstandFileRequest(BaseModel):
    thread_id: str = Field(..., description="Unique identifier for the artifacts session or thread.")
    user_goal: str = Field(..., description="Goal of the user to guide the summarization.")
    artifact: ArtifactSpec
    max_bytes: Optional[int] = Field(
        default=None,
        ge=1024,
        le=500_000,
        description="Override for the maximum bytes to read from the artifact when summarising.",
    )


class UnderstandFileResponse(BaseModel):
    status: str = Field(..., description="logged, duplicate, too_large, unsupported, or error.")
    message: Optional[str] = None
    summary: Optional[str] = None
    log_path: Optional[str] = None
    log_entry: Optional[str] = None
    artifact_size: Optional[int] = None
    artifact_type: Optional[str] = None
    presigned_url: Optional[str] = None
    truncated: bool = False
