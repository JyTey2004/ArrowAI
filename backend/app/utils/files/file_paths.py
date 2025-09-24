import pathlib, os
from app.tools.sandbox import sandbox

TMP_ROOT = sandbox.base_tmp.resolve()

def run_dir(run_id: str) -> pathlib.Path:
    p = TMP_ROOT / run_id
    p.mkdir(parents=True, exist_ok=True)
    return p

def cel_path(run_id: str) -> pathlib.Path:
    return run_dir(run_id) / "CEL.md"

def public_base_path(websocket) -> str:
    # Prefer env override if you front a proxy: e.g. http(s)://api.myhost.com
    env = os.getenv("PUBLIC_BASE_URL")
    if env:
        return env.rstrip("/")
    host = websocket.headers.get("host", "localhost:8000")
    scheme = "https" if websocket.headers.get("x-forwarded-proto", "http") == "https" else "http"
    return f"{scheme}://{host}"

