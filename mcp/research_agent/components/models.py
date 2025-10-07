
from typing import Optional, List
from pydantic import BaseModel, Field


class File(BaseModel):
    name: str
    path: str = Field(..., description="Full path of the file e.g s3://bucket/key")
    description: Optional[str] = None
    size: Optional[int] = None

class ResearchRequest(BaseModel):
    task: str = Field(..., description="User goal / topic")
    thread_id: str = Field(..., description="Unique ID for this research thread")
    files_in: Optional[List[File]] = Field(
        default_factory=list,
        description="List of input files already available (e.g. downloaded from S3) with keys: name, path, size",
    )

class QuestionPlan(BaseModel):
    rationale: Optional[str] = Field(
        default=None,
        description="High level reasoning connecting artifacts to the proposed questions",
    )
    questions: List[str] = Field(
        min_items=1,
        max_items=3,
        description="Next research questions ranked by importance",
    )
    
class AnalysisResult(BaseModel):
    key_findings: str = Field(
        ..., description="Summary of key findings from the analysis"
    )
    gaps: str = Field(
        ..., description="Identified gaps or unknowns in the analysis"
    )
    artifacts: List[File] = Field(
        default_factory=list,
        description="List of relevant artifacts (files) generated or referenced during the analysis"
    )
