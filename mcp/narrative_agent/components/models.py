from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class File(BaseModel):
    name: str
    path: str = Field(..., description="Full path of the file (e.g. s3://bucket/key)")
    description: Optional[str] = None
    size: Optional[int] = None


class NarrativeRequest(BaseModel):
    task: str = Field(..., description="User goal / topic for the narrative")
    thread_id: str = Field(..., description="Unique ID for this narrative thread")
    audience: Optional[str] = Field(
        default=None,
        description="Optional description of the target audience (e.g. executives, sales leadership)",
    )
    tone: Optional[str] = Field(
        default=None,
        description="Optional tone or style guidelines (e.g. data-driven, persuasive, concise)",
    )
    files_in: List[File] = Field(
        default_factory=list,
        description="Artifacts already available (typically S3 paths) with metadata about size and description.",
    )


class NarrativeArtifact(BaseModel):
    name: str
    path: str
    description: Optional[str] = None
    size: Optional[int] = None


class NarrativeOutput(BaseModel):
    narrative_md: str = Field(..., description="Full narrative in markdown format.")
    executive_summary_md: str = Field(..., description="Executive summary in markdown format.")
    talking_points_md: Optional[str] = Field(
        default=None,
        description="Optional short bullet list of talking points.",
    )
    artifacts: List[NarrativeArtifact] = Field(
        default_factory=list,
        description="Artifacts generated during narrative composition (e.g. uploaded markdown files).",
    )

