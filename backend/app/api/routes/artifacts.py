# app/api/routes/artifacts.py
"""
Artifacts API

Expose files created under the sandbox run directory so clients can browse and download
artifacts that appear in CEL.md / sandbox results.

Endpoints
---------
GET  /artifacts/{run_id}                      -> list all files (recursive) with metadata + download URLs
GET  /artifacts/{run_id}/download             -> stream a specific file (query: path=<relative path>)

Security notes
--------------
- Paths are strictly constrained to the sandbox's run directory (no path traversal).
- Returns 404 for missing or out-of-scope files.
- Intended for local/demo use; add auth before internet exposure.
"""
from __future__ import annotations

import hashlib
import mimetypes
from typing import Any, Dict, List
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse


import logging
from app.tools.sandbox import sandbox

router = APIRouter()

logger = logging.getLogger(__name__)


def _run_dir(run_id: str):
    rd = sandbox.base_tmp.resolve() / run_id
    rd.mkdir(parents=True, exist_ok=True)
    return rd


def _index_artifacts(run_id: str) -> List[Dict[str, Any]]:
    rd = _run_dir(run_id)
    items: List[Dict[str, Any]] = []
    for p in rd.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(rd)
        try:
            data = p.read_bytes()
        except Exception:
            # unreadable files are skipped
            continue
        items.append({
            "name": p.name,
            "path": str(rel).replace("\\", "/"),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()[:12],
            "content_type": mimetypes.guess_type(p.name)[0] or "application/octet-stream",
        })
    return items


@router.get("/{run_id}")
async def list_artifacts(run_id: str, request: Request):
    """List all artifacts for a given run_id with download URLs."""
    items = _index_artifacts(run_id)
    base = str(request.base_url).rstrip("/")
    for it in items:
        it["download_url"] = f"{base}/artifacts/{run_id}/download?path={quote(it['path'])}"
    return JSONResponse(items)


@router.get("/{run_id}/download")
async def download_artifact(run_id: str, path: str = Query(..., description="Relative path within the run directory")):
    """Download/stream an artifact. Query param 'path' must be relative to the run dir."""
    logger.info(f"Download request for run_id={run_id}, path={path}")
    rd = _run_dir(run_id)
    # Normalize + prevent traversal
    abs_target = (rd / path).resolve()
    # temporarily add just before the 404 raise:
    print({"rd": str(rd), "path": path, "abs": str(abs_target), "exists": abs_target.exists()})

    if not str(abs_target).startswith(str(rd)): 
        raise HTTPException(status_code=400, detail="Invalid path")
    if not abs_target.exists() or not abs_target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = mimetypes.guess_type(abs_target.name)[0] or "application/octet-stream"
    return FileResponse(abs_target, media_type=media_type, filename=abs_target.name)
