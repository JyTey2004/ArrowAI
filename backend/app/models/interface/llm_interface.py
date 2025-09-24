
class LLMClient:
    """Minimal LLM interface. Implement .generate(prompt) to return text."""
    def generate(self, prompt: str) -> str:  # pragma: no cover (interface)
        raise NotImplementedError
