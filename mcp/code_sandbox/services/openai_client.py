import os, base64, mimetypes, pathlib, io
from typing import Any, Iterable, List, Optional, Union, Dict

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ---------- Helpers ----------
def _is_http_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")

def _guess_mime(path: str) -> str:
    mt, _ = mimetypes.guess_type(path)
    return mt or "application/octet-stream"

def _to_data_url(content: bytes, mime: str) -> str:
    b64 = base64.b64encode(content).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _read_bytes(obj: Union[str, bytes, io.BytesIO, "PIL.Image.Image"]) -> tuple[bytes, str]:
    """
    Accepts:
      - str path
      - bytes
      - BytesIO
      - PIL.Image.Image (if Pillow installed)
    Returns: (raw_bytes, mime_type_guess)
    """
    if isinstance(obj, bytes):
        return obj, "application/octet-stream"
    if isinstance(obj, io.BytesIO):
        return obj.getvalue(), "application/octet-stream"
    try:
        from PIL.Image import Image  # type: ignore
        if isinstance(obj, Image):
            buf = io.BytesIO()
            obj.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
    except Exception:
        pass
    if isinstance(obj, str):
        p = pathlib.Path(obj)
        data = p.read_bytes()
        return data, _guess_mime(p.name)
    raise TypeError(f"Unsupported image/file object: {type(obj)}")

def _ext(path: str) -> str:
    return pathlib.Path(path).suffix.lower()

# ---------- Client ----------
class OpenAIClient:
    def __init__(self, *, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL") or None,
        )

    # --- FILE UPLOAD (PDF/CSV/etc.) ---
    def upload_file(self, path: str, purpose: str = "user_data") -> str:
        with open(path, "rb") as f:
            file = self.client.files.create(file=f, purpose=purpose)
        return file.id

    # --- MULTIMODAL GENERATE ---
    def generate(
        self,
        *,
        model: str,
        # high-level inputs
        system: Optional[str] = None,
        text: Optional[str] = None,
        images: Optional[Iterable[Union[str, bytes, io.BytesIO, "PIL.Image.Image"]]] = None,
        image_urls: Optional[Iterable[str]] = None,
        files: Optional[Iterable[Union[str, Dict[str, Any]]]] = None,  # paths or already-uploaded {"file_id": "..."}
        # responses API extras
        instructions: Optional[str] = None,  # alias for system
        max_output_tokens: Optional[int] = 100000,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        # NEW: control what gets inlined as text instead of uploaded
        inline_file_exts: Optional[set[str]] = None,   # defaults to {".md", ".log", ".txt"}
        inline_file_names: Optional[set[str]] = None,  # defaults to {"CEL.md"}
    ):
        """
        Build a Responses API request with text + images + files.
        - images: local path/bytes/BytesIO/PIL -> data URL; image_urls: http(s) links
        - files: local paths (auto-upload) or dicts with {"file_id": "..."} to be referenced
        - CEL.md (and any .md by default) are **inlined as text** (no upload) for maximal compatibility
        """

        # Defaults for inlining
        inline_file_exts = inline_file_exts or {".md", ".log", ".txt"}
        inline_file_names = inline_file_names or {"CEL.md"}

        # 1) Build messages for 'input' (Responses API)
        messages: List[Dict[str, Any]] = []

        sys_text = instructions or system
        if sys_text:
            messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": sys_text}],
            })

        user_content: List[Dict[str, Any]] = []
        if text:
            user_content.append({"type": "input_text", "text": text})

        # 2) Images (URLs or local -> data URL)
        if image_urls:
            for url in image_urls:
                if not _is_http_url(url) and not url.startswith("data:"):
                    raise ValueError(f"image_urls must be http(s) or data URLs: {url}")
                user_content.append({"type": "input_image", "image_url": {"url": url}})

        if images:
            for img in images:
                raw, mime = _read_bytes(img)
                data_url = _to_data_url(raw, mime)
                user_content.append({"type": "input_image", "image_url": {"url": data_url}})

        # 3) Files: inline CEL.md/.md as text; upload supported formats
        if files:
            for f in files:
                # Already-uploaded file reference
                if isinstance(f, dict) and "file_id" in f:
                    user_content.append({"type": "input_file", "file_id": f["file_id"]})
                    continue

                if not isinstance(f, str):
                    raise TypeError("files[] must be paths or {'file_id': '...'}")

                p = pathlib.Path(f)
                ext = _ext(f)

                # Inline as text for CEL.md or inline-able extensions
                if p.name in inline_file_names or ext in inline_file_exts:
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore")
                    except UnicodeDecodeError:
                        # fallback to bytes → base64 in a text block
                        content = p.read_bytes().decode("utf-8", errors="ignore")
                    # Make it obvious for the model what file this is
                    banner = f"BEGIN {p.name}\n{content}\nEND {p.name}"
                    user_content.append({"type": "input_text", "text": banner})
                    continue

                # Otherwise upload and reference as input_file
                purpose = "vision" if ext in {".png", ".jpg", ".jpeg", ".webp"} else "user_data"
                fid = self.upload_file(f, purpose=purpose)
                user_content.append({"type": "input_file", "file_id": fid})

        # Only add user message if something is there
        if user_content:
            messages.append({"role": "user", "content": user_content})

        # 4) Create request
        kwargs: Dict[str, Any] = {
            "model": model,
            "input": messages if messages else (text or ""),
        }
        if max_output_tokens is not None:
            kwargs["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if metadata is not None:
            kwargs["metadata"] = metadata

        return self.client.responses.create(stream=True, **kwargs) if stream else self.client.responses.create(**kwargs)

    # Convenience: get plain text (handles Responses API shape)
    @staticmethod
    def output_text(response) -> str:
        try:
            return response.output_text  # some SDKs expose this directly
        except Exception:
            pass
        try:
            for out in response.output:  # fallback walk
                if out.type == "message":
                    for c in out.message.content:
                        if c.type == "output_text":
                            return c.text
        except Exception:
            pass
        return ""
