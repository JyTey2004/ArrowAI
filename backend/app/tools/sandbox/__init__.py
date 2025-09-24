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
code_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_CODE_MODEL","gpt-4.1-mini"),
    temperature=0.1,
    system="You are a senior Python engineer. Write ONE Python cell only. Use CEL.md context.",
)
eval_llm = LLMAdapter(
    client=_oai,
    model=os.getenv("SANDBOX_EVAL_MODEL","gpt-4.1-mini"),
    temperature=0.0,
    system="Strict evaluator. Return exactly one line: PASS/FAIL — reason; completeness, correctness, evidence, hygiene (0..1).",
)
