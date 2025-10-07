from typing import Any, Dict, Iterable, List, Optional, Union

from services.openai_client import OpenAIClient


class LLMAdapter:
    """
    Bridges a simple generate/response API to the OpenAI client used by our agents.
    """

    def __init__(
        self,
        client: Optional[OpenAIClient] = None,
        *,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.2,
        system: Optional[str] = None,
    ) -> None:
        self.oai = client or OpenAIClient()
        self.model = model
        self.temperature = temperature
        self.system = system or "You are a concise, expert business writer."

    def generate(
        self,
        prompt: str,
        *,
        files: Optional[Iterable[Union[str, Dict[str, Any]]]] = None,
        images: Optional[Iterable[Union[str, bytes]]] = None,
        image_urls: Optional[Iterable[str]] = None,
    ) -> str:
        response = self.oai.generate(
            model=self.model,
            system=self.system,
            text=prompt,
            files=files,
            images=images,
            image_urls=image_urls,
            temperature=self.temperature,
        )
        return self.oai.output_text(response) or ""

    def response(self, prompt: List[Dict[str, Any]]) -> str:
        resp = self.oai.response(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": self.system}],
                },
                *prompt,
            ],
            temperature=self.temperature,
        )
        return self.oai.output_text(resp) or ""

