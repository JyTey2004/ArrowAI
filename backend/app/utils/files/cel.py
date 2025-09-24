from app.utils.files.file_paths import cel_path

def read_cel(run_id: str, limit: int = 20000) -> str:
    cel = cel_path(run_id)
    if not cel.exists():
        return ""
    t = cel.read_text(encoding="utf-8", errors="ignore")
    return t if len(t) <= limit else t[-limit:]


def append_cel(run_id: str, title: str, body: str) -> None:
    cel = cel_path(run_id)
    cel.parent.mkdir(parents=True, exist_ok=True)
    header = "# Context Engineering Log (CEL)\n\n"
    prev = cel.read_text() if cel.exists() else header
    block = f"## Step: {title}\n\n{body}\n\n"
    cel.write_text(prev + block)