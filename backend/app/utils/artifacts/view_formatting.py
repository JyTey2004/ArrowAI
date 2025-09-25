from urllib.parse import quote

def _strip_run_prefix(p: str, run_id: str) -> str:
    pref = f"{run_id}/"
    return p[len(pref):] if p.startswith(pref) else p

def add_view_urls(artifacts, run_id: str, base: str):
    out = []
    for a in artifacts or []:
        rel = _strip_run_prefix(str(a.get("path", "")), run_id)
        a2 = dict(a)
        a2["path"] = rel
        a2["view_url"] = f"{base}/artifacts/{run_id}/download?path={quote(rel)}"
        out.append(a2)
    return out

def views_markdown(artifacts, run_id: str, base: str) -> str:
    exts = {".parquet", ".csv", ".pdf", ".html", ".png", ".pptx", ".md"}
    import os
    lines = []
    for a in artifacts or []:
        name = a.get("name", "")
        rel = _strip_run_prefix(str(a.get("path", "")), run_id)
        if os.path.splitext(name)[1].lower() in exts:
            url = f"{base}/artifacts/{run_id}/download?path={quote(rel)}"
            # Build markdown link ourselves; LLM won’t rewrite this string
            lines.append(f"[{name}]({url})")
    return "\n".join(lines) or "(no viewable artifacts yet)"