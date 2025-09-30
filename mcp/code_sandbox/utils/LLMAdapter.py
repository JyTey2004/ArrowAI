from typing import Any, Dict, Iterable, List, Optional, Union
from components.executor import LLMClient
from services.openai_client import OpenAIClient

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
        max_output_tokens: int=800,
    ) -> str:
        resp = self.oai.generate(
            model=self.model, 
            system=self.system, 
            text=prompt,
            files=files, 
            images=images, 
            image_urls=image_urls,
            temperature=self.temperature, 
            max_output_tokens=max_output_tokens,
        )
        return self.oai.output_text(resp) or ""