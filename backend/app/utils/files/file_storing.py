from typing import Any, Dict, List
import pathlib
import base64

def save_ws_files(rd: pathlib.Path, files: List[Dict[str, Any]]) -> List[str]:
    """
    Accepts items like:
      {"name": "...", "content": "...", "encoding": "text" | "base64"}
    Writes under tmp/<run_id>/ and returns absolute paths.
    """
    saved = []
    for f in files or []:
        name = (f.get("name") or "").strip()
        if not name:
            continue
        enc = (f.get("encoding") or "text").lower()
        content = f.get("content")
        if content is None:
            continue
        out = rd / name
        if enc == "base64":
            import base64
            out.write_bytes(base64.b64decode(content))
        else:  # "text" or anything else -> treat as text
            out.write_text(str(content), encoding="utf-8")
        saved.append(str(out))
    return saved


def save_b64_files(rd: pathlib.Path, items: List[Dict[str, str]]) -> List[str]:
    """Accepts [{"name","b64"}] and writes under tmp/<run_id>/, returning paths."""
    saved: List[str] = []
    for it in items:
        name, b64 = it.get("name"), it.get("b64")
        if not name or not b64:
            continue
        data = base64.b64decode(b64)
        out = rd / name
        out.write_bytes(data)
        saved.append(str(out))
    return saved