from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict

class SandboxExecIn(BaseModel):
    code: str = Field(..., description="Python cell to execute")
    language: str = "python"
    files_in: Optional[List[Dict[str, str]]] = None  # reserved for future
    timeout_s: Optional[int] = None
    task: Optional[str] = None                        # used by evaluator LLM
    pip: Optional[List[str]] = None                  # packages to install first
    use_llm_writer: bool = False                     # ask LLM to write/transform code
    repair_attempts: int = 2                  # how many times to try LLM repair if enabled

class FileMeta(BaseModel):
    path: str
    size: int
    sha256: str
    name: str

class SandboxExecOut(BaseModel):
    ok: bool
    stdout: str
    stderr: str
    display: Optional[Any] = None
    files_out: List[FileMeta]
    summary: str
