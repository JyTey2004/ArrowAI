# app/api/routes/health.py
from fastapi import APIRouter, Request
from app.core.version import VERSION
from app.core.config import settings
import time

router = APIRouter()

@router.get("/health")
async def health(request: Request):
    """
    Lightweight liveness & config probe.
    """
    start = getattr(request.app.state, "start_time", None)
    uptime_s = round(time.time() - start, 3) if start else None

    return {
        "status": "ok",
        "service": "ArrowAI Backend",
        "version": VERSION,
        "env": settings.ENV,
        "uptime_s": uptime_s,
    }

# Optional probes commonly used by k8s:
@router.get("/_live")
async def liveness():
    return {"status": "alive"}

@router.get("/_ready")
async def readiness():
    # Later: add checks for tmp store writeability, sandbox spawn, etc.
    return {"status": "ready"}
