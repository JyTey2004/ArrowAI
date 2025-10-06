import re

def _extract_python(code: str) -> str:
    """
    If the LLM returned Markdown-fenced code (``` or ```python), extract the inner code.
    Otherwise, return the original string. Also strips leading/trailing whitespace.
    """
    if "```" not in code:
        return code.strip()
    # Prefer a language fence block if present
    m = re.search(r"```(?:python|py)?\s*\n(.*?)\n```", code, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: remove any backticks naively
    return code.replace("```python", "").replace("```", "").strip()
