from fastapi import APIRouter, HTTPException, Query
from app.models.tools.sandbox import SandboxExecIn, SandboxExecOut, FileMeta
from app.tools.sandbox import sandbox, code_llm, eval_llm
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter()

@router.post("/exec", response_model=SandboxExecOut)
def sandbox_exec(
    payload: SandboxExecIn,
    run_id: str = Query(..., description="Unique session id (kernel & tmp namespace)"),
    use_eval_llm: bool = Query(True, description="Evaluate outputs vs task and update CEL.md"),
    use_code_llm: bool = Query(False, description="Let LLM write/transform code before execution"),
):
    try:
        # Respect route switches over body defaults
        payload.use_llm_writer = use_code_llm or payload.use_llm_writer

        result = sandbox.exec_cell(
            run_id=run_id,
            req=payload,                              # dataclass compatibility via same fields
            code_llm=code_llm if payload.use_llm_writer else None,
            eval_llm=eval_llm if (use_eval_llm and payload.task) else None,
        )

        return SandboxExecOut(
            ok=result.ok,
            stdout=result.stdout,
            stderr=result.stderr,
            display=result.display,
            files_out=[FileMeta(**f) for f in result.files_out],
            summary=result.summary,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        log.error("sandbox.exec failed", exc_info=True)
        raise HTTPException(status_code=500, detail="sandbox.exec internal error")
