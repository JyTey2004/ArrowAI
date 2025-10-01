from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

DEFAULT_TTL = 1800  # seconds

# ----------------- Models (IO schemas) -----------------

class FileIn(BaseModel):
    name: str
    path: str = Field(..., description="Full path of the file e.g s3://bucket/key")
    size: Optional[int] = None


class CodeExecInput(BaseModel):
    thread_id: str = Field(..., description="Unique ID for the session")
    # code: Optional[str] = Field(None, description="Code to execute")
    task: str = Field(..., description="Natural language description of the task to accomplish with the code")
    timeout_s: Optional[int] = 30
    # pip: Optional[List[str]] = None
    files_in: Optional[List[FileIn]] = Field(default_factory=list, description="List of input files to be downloaded before execution")
    max_steps: int = 7
    repair_attempts: int = 2

class CreateSessionIn(BaseModel):
    run_id: Optional[str] = None
    ttl_seconds: Optional[int] = DEFAULT_TTL
    language: str = "python"

class CreateSessionOut(BaseModel):
    run_id: str
    workdir: str
    cel_path: str
    expires_at: str

class ExecCellIn(BaseModel):
    run_id: str
    code: Optional[str] = None
    task: Optional[str] = None
    timeout_s: Optional[int] = 30
    pip: Optional[List[str]] = None
    use_llm_writer: bool = False
    repair_attempts: int = 2

class FileSpec(BaseModel):
    name: str
    path: str
    size: int
    sha256: str

class ExecCellOut(BaseModel):
    ok: bool
    code: Optional[Dict[str, Any]]
    stdout: str
    stderr: str
    display: Optional[Any]
    files_out: List[FileSpec]
    summary: str

class EnsurePackagesIn(BaseModel):
    run_id: str
    packages: List[str]

class EnsurePackagesOut(BaseModel):
    ok: bool
    log: str

class ListFilesIn(BaseModel):
    run_id: str
    path: str = "."

class FileEntry(BaseModel):
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified_at: Optional[str] = None

class ListFilesOut(BaseModel):
    entries: List[FileEntry]

class ReadFileIn(BaseModel):
    run_id: str
    path: str

class ReadFileOut(BaseModel):
    path: str
    content_base64: str

class WriteFileIn(BaseModel):
    run_id: str
    path: str
    content_base64: str
    overwrite: bool = False

class WriteFileOut(BaseModel):
    ok: bool

class ListArtifactsIn(BaseModel):
    run_id: str

class ListArtifactsOut(BaseModel):
    artifacts: List[FileSpec]

class GetCelIn(BaseModel):
    run_id: str

class GetCelOut(BaseModel):
    cel_markdown: str

class KillSessionIn(BaseModel):
    run_id: str
    delete_files: bool = False

class KillSessionOut(BaseModel):
    terminated: bool