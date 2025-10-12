# Requirements:
# - LibreOffice installed and `soffice` on PATH
# - For PDF->PNG fallback: pip install "pymupdf>=1.23.0"

import os
import io
import shlex
import shutil
import subprocess
import tempfile
from typing import List, Tuple, Optional

def _run(cmd: str) -> None:
    """Run a shell command and raise on non-zero exit."""
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

def _check_soffice() -> str:
    path = shutil.which("soffice") or shutil.which("soffice.bin")
    if not path:
        raise EnvironmentError("LibreOffice 'soffice' not found on PATH.")
    return path

def convert_pptx_to_png_bytes(
    pptx_bytes: bytes,
    *,
    width_hint_px: Optional[int] = None,   # used by direct PNG export (some builds ignore)
    fallback_dpi: int = 300,               # used by PDF->PNG
    try_direct_png: bool = True,           # True: PPTX->PNG ; False: go straight to PDF->PNG
) -> List[bytes]:
    """
    Convert a PPTX blob to a list of PNG byte blobs (one per slide) using LibreOffice.
    Nothing is persisted outside temp dirs (auto-cleaned).
    """
    soffice = _check_soffice()

    with tempfile.TemporaryDirectory(prefix="lo_pptx_") as tmpdir:
        in_pptx = os.path.join(tmpdir, "in.pptx")
        with open(in_pptx, "wb") as f:
            f.write(pptx_bytes)

        # 1) Try direct PNG export if requested
        if try_direct_png:
            # Some LibreOffice builds accept filter options; most ignore width/height hints.
            # If your build supports it, you can append something like :X-DPI=220
            cmd = f'{shlex.quote(soffice)} --headless --convert-to "png:impress_png_Export" --outdir {shlex.quote(tmpdir)} {shlex.quote(in_pptx)}'
            try:
                _run(cmd)
                # LibreOffice writes one PNG per slide, typically named in-<N>.png or in.png, in_1.png, etc.
                # Collect any .png written to tmpdir, sorted by name.
                png_paths = sorted(
                    [os.path.join(tmpdir, p) for p in os.listdir(tmpdir) if p.lower().endswith(".png")]
                )
                if png_paths:
                    out = []
                    for p in png_paths:
                        with open(p, "rb") as imgf:
                            out.append(imgf.read())
                    return out
                # If no PNGs produced, fall through to PDF route
            except Exception:
                # Fall back to PDF route
                pass

        # 2) Fallback: PPTX -> PDF
        out_pdf = os.path.join(tmpdir, "out.pdf")
        cmd_pdf = f'{shlex.quote(soffice)} --headless --convert-to pdf --outdir {shlex.quote(tmpdir)} {shlex.quote(in_pptx)}'
        _run(cmd_pdf)
        if not os.path.exists(out_pdf):
            raise RuntimeError("LibreOffice did not produce a PDF during fallback.")

        # 3) PDF -> PNG bytes at chosen DPI (no persistent files)
        try:
            import fitz  # PyMuPDF
        except Exception as e:
            raise RuntimeError(
                "PDF->PNG fallback requires PyMuPDF. Install with: pip install pymupdf"
            ) from e

        zoom = fallback_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        out_bytes: List[bytes] = []
        with fitz.open(out_pdf) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                buf = io.BytesIO()
                pix.save(buf, format="PNG")
                out_bytes.append(buf.getvalue())
        return out_bytes


# --- Example usage with your SlideQAAgent (no files left behind) ---

# pptx_bytes = ...  # load from S3, upload, etc.
# png_list = convert_pptx_to_png_bytes(pptx_bytes, try_direct_png=True, fallback_dpi=300)
# qa = SlideQAAgent(llm)
# for i, png in enumerate(png_list, start=1):
#     report = qa.evaluate(
#         slide=png,  # <-- bytes
#         layout=layout_json,
#         slide_outline=slide_outline_json,
#         insight_summary=insight_summary_json,
#         cycle=i,
#         max_cycles=len(png_list),
#     )
#     print(f"Slide {i} report:", report)
