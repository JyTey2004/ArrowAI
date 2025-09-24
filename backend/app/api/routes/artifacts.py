# app/api/routes/artifacts.py
"""
Artifacts API

Expose files created under the sandbox run directory so clients can browse and download
artifacts that appear in CEL.md / sandbox results.

Endpoints
---------
GET  /artifacts/{run_id}                      -> list all files (recursive) with metadata + download URLs
GET  /artifacts/{run_id}/download             -> stream a specific file (query: path=<relative path>)
GET  /artifacts/{run_id}/view                 -> stream a specific file with inline Content-Disposition (query: path=<relative path>)
HEAD /artifacts/{run_id}/view                 -> fetch metadata (no body) for a specific file (query: path=<relative path>)

Security notes
--------------
- Paths are strictly constrained to the sandbox's run directory (no path traversal).
- Returns 404 for missing or out-of-scope files.
- Intended for local/demo use; add auth before internet exposure.
"""
# app/api/routes/artifacts.py
from __future__ import annotations

import hashlib
import mimetypes
from typing import Any, Dict, List
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response

import logging
from app.tools.sandbox import sandbox

router = APIRouter()
logger = logging.getLogger(__name__)


def _run_dir(run_id: str):
    rd = sandbox.base_tmp.resolve() / run_id
    rd.mkdir(parents=True, exist_ok=True)
    return rd

# NEW: safer resolver (prevents traversal without fragile string prefix checks)
def _resolve_target(run_id: str, rel_path: str):
    rd = _run_dir(run_id)
    abs_target = (rd / rel_path).resolve()
    try:
        abs_target.relative_to(rd)  # raises ValueError if outside rd
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    return rd, abs_target


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
    """List all artifacts for a given run_id with download & view URLs."""
    items = _index_artifacts(run_id)
    base = str(request.base_url).rstrip("/")
    for it in items:
        q = quote(it["path"])
        it["download_url"] = f"{base}/artifacts/{run_id}/download?path={q}"
        # NEW: inline-friendly URL your UI can use directly in <img>, <video>, <object>, etc.
        it["view_url"] = f"{base}/artifacts/{run_id}/view?path={q}"
    return JSONResponse(items)


@router.get("/{run_id}/download")
async def download_artifact(run_id: str, path: str = Query(..., description="Relative path within the run directory")):
    """Download/stream an artifact as an attachment."""
    logger.info(f"Download request for run_id={run_id}, path={path}")
    _, abs_target = _resolve_target(run_id, path)

    if not abs_target.exists() or not abs_target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = mimetypes.guess_type(abs_target.name)[0] or "application/octet-stream"
    # FileResponse sets 'attachment' when filename is provided; that’s what we want here.
    return FileResponse(abs_target, media_type=media_type, filename=abs_target.name)


# NEW: inline view endpoint (good for <img src>, <object data>, <iframe src>, etc.)
@router.get("/{run_id}/view")
async def view_artifact(
    run_id: str,
    request: Request,
    path: str = Query(..., description="Relative path within the run directory"),
    # optional toggle if you ever want to force a download from the same endpoint
    download: bool = False,
):
    """Stream an artifact with inline Content-Disposition and cache headers."""
    logger.info(f"View request for run_id={run_id}, path={path}")
    _, abs_target = _resolve_target(run_id, path)

    if not abs_target.exists() or not abs_target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = mimetypes.guess_type(abs_target.name)[0] or "application/octet-stream"

    # Lightweight weak ETag based on (mtime,size) — avoids hashing big files
    st = abs_target.stat()
    etag = f'W/"{st.st_mtime_ns:x}-{st.st_size:x}"'

    # If client already has it cached
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    # Inline vs attachment
    disp = "attachment" if download else "inline"
    headers = {
        "ETag": etag,
        # Tune caching as you like; demo-friendly default:
        "Cache-Control": "public, max-age=3600",
        "Content-Disposition": f'{disp}; filename="{abs_target.name}"',
        # Optional hint that we support ranges (useful for media scrubbing)
        "Accept-Ranges": "bytes",
    }

    # Starlette's FileResponse supports efficient file sending and Range requests.
    return FileResponse(abs_target, media_type=media_type, headers=headers)


# OPTIONAL (nice for quick checks): HEAD to fetch metadata without body
@router.head("/{run_id}/view")
async def head_view_artifact(
    run_id: str,
    path: str = Query(..., description="Relative path within the run directory"),
):
    _, abs_target = _resolve_target(run_id, path)
    if not abs_target.exists() or not abs_target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    st = abs_target.stat()
    etag = f'W/"{st.st_mtime_ns:x}-{st.st_size:x}"'
    media_type = mimetypes.guess_type(abs_target.name)[0] or "application/octet-stream"
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=3600",
        "Content-Type": media_type,
        "Content-Length": str(st.st_size),
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{abs_target.name}"',
    }
    return Response(status_code=200, headers=headers)
