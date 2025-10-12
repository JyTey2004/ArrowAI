

from typing import Any, Dict, Iterable, List, Optional, Union
from services.openai_client import OpenAIClient

class LLMClient:
    """Minimal LLM interface. Implement .generate(prompt) to return text."""
    def generate(self, prompt: str) -> str:  # pragma: no cover (interface)
        raise NotImplementedError

class LLMAdapter(LLMClient):
    """
    Bridges the sandbox's LLMClient interface to your OpenAIClient.generate().
    You can pass extra multimodal context (images, files) per call.
    """
    def __init__(self, client: Optional[OpenAIClient]=None, *, model: str="gpt-4.1-mini",
                 temperature: float=0.2, system: Optional[str]=None):
        self.oai = client or OpenAIClient()
        self.model = model
        self.temperature = temperature
        self.system = system or "Be concise and correct. Output only what is asked."

    def generate(
        self, 
        prompt: str, 
        *, 
        files: Optional[Iterable[Union[str, Dict[str, Any]]]]=None,
        images: Optional[Iterable[Union[str, bytes]]]=None, 
        image_urls: Optional[Iterable[str]]=None,
    ) -> str:
        resp = self.oai.generate(
            model=self.model, 
            system=self.system, 
            text=prompt,
            files=files, 
            images=images, 
            image_urls=image_urls,
            temperature=self.temperature, 
        )
        return self.oai.output_text(resp) or ""
    
    def response(
        self, 
        prompt
    ) -> str:
        resp = self.oai.response(
            model=self.model,
            input=[
                 {
                    "role": "system",
                    "content": [{"type": "input_text", "text": self.system}],
                 },
                 *prompt
            ],
            temperature=self.temperature, 
        )
        return self.oai.output_text(resp) or ""