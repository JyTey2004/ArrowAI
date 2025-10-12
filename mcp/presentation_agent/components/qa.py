"""Slide QA agent that critiques rendered slides and emits structured QA reports."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List, Optional

from components.models import SlideQAReport
from utils.pptx_to_png import convert_pptx_to_png_bytes
from utils.LLMAdapter import LLMAdapter
import io

log = logging.getLogger(__name__)


class SlideQAAgent:
    """LLM-backed QA agent that critiques rendered slides."""

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    def evaluate(
        self,
        *,
        slide: Any,
        layout: Dict[str, Any],
        slide_outline: Dict[str, Any],
        insight_summary: Dict[str, Any],
        qa_report: Optional[SlideQAReport],
        cycle: int,
        max_cycles: int,
    ) -> SlideQAReport:
        png_bytes = convert_pptx_to_png_bytes(slide, try_direct_png=True, fallback_dpi=300)[0]
        messages = self._build_messages(
            slide=png_bytes,
            layout=layout,
            slide_outline=slide_outline,
            insight_summary=insight_summary,
            qa_report=qa_report,
            cycle=cycle,
            max_cycles=max_cycles,
        )
        raw = self._llm.response(messages)
        report_dict = self._parse_json(raw)
        report = SlideQAReport(**report_dict)
        log.debug("QA cycle %s/%s produced report: %s", cycle, max_cycles, report_dict)
        return report

    def _build_messages(
        self,
        *,
        slide: Any,
        layout: Dict[str, Any],
        insight_summary: Dict[str, Any],
        slide_outline: Dict[str, Any],
        qa_report: Optional[SlideQAReport],
        cycle: int,
        max_cycles: int,
    ) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = []
        if qa_report:
            content.append({"type": "input_text", "text": f"Previous QA report (JSON):\n{json.dumps(qa_report.model_dump(), indent=2, ensure_ascii=False)}"})
        context = {
            "cycle": cycle,
            "max_cycles": max_cycles,
            "layout": layout,
            "slide_outline": slide_outline,
            "insight_summary": insight_summary,
        }
        context_json = json.dumps(context, indent=2, ensure_ascii=False)
        content.append({"type": "input_text", "text": f"Review context (JSON):\n{context_json}"})

        if slide:
            image_b64 = base64.b64encode(slide).decode("utf-8")
            content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{image_b64}",
            })
        else:
            raise ValueError("QA evaluation requires an image reference.")

        return [{"role": "user", "content": content}]

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("QA agent did not return JSON.")
        payload = json.loads(text[start : end + 1])
        payload.setdefault("issues", [])
        return payload


