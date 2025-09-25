from .executor import CodeSandbox
from app.services.openai_client import OpenAIClient
from app.utils.adapters.LLMAdapter import LLMAdapter
import os, pathlib

BASE_TMP = os.getenv(
    "SANDBOX_TMP_DIR",
    str(pathlib.Path(__file__).resolve().parents[3] / "tmp")  # ~/ArrowAI/backend/tmp
)

sandbox = CodeSandbox(base_tmp_dir=BASE_TMP)

_oai = OpenAIClient()

CODE_SYSTEM = (
    "You write a single Python cell to satisfy the TASK.\n"
    "Honor EVIDENCE: print exactly the requested diagnostics.\n"
    "Honor ARTIFACTS: write the named files and print their paths after writing.\n"
    "Never assume schema: if columns are unknown, inspect df first. If a date column is expected but not confirmed, try common names ('datum','date','month','period').\n"
    "If a required column is missing, STOP and print a clear error + available columns (do not fabricate)."
)

EVAL_SYSTEM = (
    "You evaluate and summarize code runs.\n"
    "Inputs (JSON): {task, stdout, stderr, files_out}\n"
    "Return ONE JSON object ONLY:\n"
    "{\n"
    '  "eval": "short reason (1-2 sentences)",\n'
    '  "verdict": "PASS" | "FAIL",\n'
    '  "output_summary": "<=800 chars summary of stdout (shapes, key columns, any wrote: lines); if stderr exists, include a 1-line gist>"\n'
    "}\n"
    "Rules:\n"
    "- Never invent columns or files.\n"
    "- Prefer concrete facts from stdout.\n"
    "- If stderr is non-empty, verdict is usually FAIL unless stdout clearly fulfilled the task."
)


code_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_CODE_MODEL","gpt-4.1-mini"),
    temperature=0.1,
    system=CODE_SYSTEM,
)
eval_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_EVAL_MODEL","gpt-4.1-mini"),
    temperature=0.0,
    system=EVAL_SYSTEM,
)
