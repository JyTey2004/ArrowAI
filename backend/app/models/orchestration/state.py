from pydantic import BaseModel
from typing import Any, Dict, List, Annotated
from langgraph.graph.message import add_messages


class WSState(BaseModel):
    # identity
    base: str
    run_id: str
    chat_title: str
    messages: Annotated[List[Dict[str, Any]], add_messages]
    text: str
    files: List[str]
    
    # control
    need_clarification: bool
    clarifying_question: str
    todos_md: str
    step_idx: int
    max_steps: int
    done: bool
    
    # execution artifacts
    code: Dict[str, Any]
    stdout: str
    stderr: str
    artifacts: List[Dict[str, Any]]
    answer_artifacts: List[Dict[str, Any]]
    answer: str
