"""
Outline planning primitives for the presentation agent.

This module now supports both deterministic scaffolds and LLM-backed outlines.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable, List, Optional, Sequence

from .models import (
    OutlineArtifact,
    SlideOutline,
    PresentationOutlineRequest,
    PresentationOutlineResponse,
)
from aws.s3_client import S3Client
from utils.LLMAdapter import LLMAdapter

log = logging.getLogger(__name__)


class PresentationOutlinePlanner:
    """Produce a per-slide outline that downstream steps can expand."""

    def __init__(
        self,
        llm: Optional[LLMAdapter] = None,
        *,
        s3_client: S3Client,
        min_slides: int = 12,
        max_slides: int = 18,
        allowed_artifact_exts: Sequence[str] = (".txt", ".md", ".markdown"),
    ) -> None:
        self.llm = llm
        self.s3_client = s3_client
        self.min_slides = min_slides
        self.max_slides = max_slides
        self.allowed_artifact_exts = tuple(e.lower() for e in allowed_artifact_exts)

    def plan_outline(self, request: PresentationOutlineRequest) -> PresentationOutlineResponse:
        """
        Generate a slide outline tailored to the user's narrative.

        If an LLM adapter is configured, request a strict JSON payload of slides.
        Otherwise, fall back to a deterministic scaffold.
        """
        try:
            artifacts = self._filter_artifacts(request.artifacts)
            if request.artifacts and not artifacts:
                log.info("No eligible narrative artifacts after filtering non-text inputs.")

            if not self.llm:
                return self._fallback_outline(request, artifacts)

            raw = self.llm.generate(self._build_prompt(request, artifacts))
            payload = self._parse_outline_response(raw)
            return self._build_response_from_payload(payload)
        except Exception as exc:
            log.warning("LLM outline generation failed (%s); using fallback scaffold.", exc)
            return self._fallback_outline(request, artifacts)

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    def _build_prompt(self, request: PresentationOutlineRequest, artifacts: Sequence[OutlineArtifact]) -> str:
        audience = request.audience or "general audience"
        desired_outcome = request.desired_outcome or "clarify the recommended action"

        artifact_block = self._format_artifacts(artifacts)

        # Strict JSON-only schema prompt that matches SlideOutline exactly
        return (
            "Plan the presentation slides as conclusion-led headlines.\n"
            f"Topic: {request.topic}\n"
            f"Audience persona: {audience}\n"
            f"Desired outcome: {desired_outcome}\n"
            "\n"
            "Reference materials:\n"
            f"{artifact_block}\n"
        )

    def _format_artifacts(self, artifacts: Iterable[OutlineArtifact]) -> str:
        formatted: List[str] = []
        for artifact in artifacts or []:
            header = f"- {artifact.name}"
            if artifact.path:
                header += f" ({artifact.path})"

            artifact_content, _ = self.s3_client.get_bytes(artifact.path) if artifact.path else (None, None)

            if artifact_content:
                artifact_content = artifact_content.decode("utf-8")

            summary = (artifact.summary or "").strip()
            if summary:
                formatted.append(f"{header}\n  Summary: {summary}")
            elif artifact_content:
                formatted.append(f"{header}\n  Excerpt: {artifact_content}")
            else:
                formatted.append(f"{header}\n  Summary: n/a")

        if not formatted:
            return "- No narrative artifacts supplied."
        return "\n".join(formatted)

    def _parse_outline_response(self, raw: str) -> dict:
        """
        Accepts either:
          { "slides": [ ... ] }
        or, defensively, a bare array [ ... ] which we wrap into { "slides": ... }.
        """
        text = raw.strip()
        # Grab the outermost JSON object/array
        start_obj, end_obj = text.find("{"), text.rfind("}")
        start_arr, end_arr = text.find("["), text.rfind("]")
        json_blob = None

        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            json_blob = text[start_obj : end_obj + 1]
            data = json.loads(json_blob)
            if isinstance(data, list):  # rare but just in case
                return {"slides": data}
            if isinstance(data, dict):
                # If the model returned extra keys, we don't fail here; we enforce later.
                if "slides" in data and isinstance(data["slides"], list):
                    return {"slides": data["slides"]}
                # If it returned a dict but slides missing, attempt to find a plausible list
                for k, v in list(data.items()):
                    if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                        return {"slides": v}
                raise ValueError("JSON object did not contain a 'slides' array.")
        elif start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            json_blob = text[start_arr : end_arr + 1]
            return {"slides": json.loads(json_blob)}

        raise ValueError("Outline LLM did not return JSON.")

    def _build_response_from_payload(self, payload: dict) -> PresentationOutlineResponse:
        slides_payload = payload.get("slides") or []
        if not isinstance(slides_payload, list):
            raise ValueError("'slides' must be an array.")

        slide_blueprints: List[SlideOutline] = []
        for idx, slide in enumerate(slides_payload, start=1):
            # Required
            slide_id = str(slide.get("slide_id") or f"S{idx:02d}").strip()
            title = str(slide.get("title") or "Untitled slide").strip()

            # Optional
            message = slide.get("message")
            message = str(message).strip() if message else None

            evidence_field = slide.get("expected_evidence") or []
            if isinstance(evidence_field, str):
                expected_evidence = [evidence_field.strip()] if evidence_field.strip() else []
            else:
                expected_evidence = [str(x).strip() for x in evidence_field if str(x).strip()]

            notes = slide.get("notes")
            notes = str(notes).strip() if notes else None

            layout = slide.get("layout")
            layout = str(layout).strip() if layout else None

            slide_blueprints.append(
                SlideOutline(
                    slide_id=slide_id,
                    title=title,
                    message=message,
                    expected_evidence=expected_evidence,
                    notes=notes,
                    layout=layout,
                )
            )

        return PresentationOutlineResponse(slides=slide_blueprints)

    def _fallback_outline(
        self,
        request: PresentationOutlineRequest,
        artifacts: Sequence[OutlineArtifact],
    ) -> PresentationOutlineResponse:
        """
        Deterministic, minimal slide set that still matches SlideOutline.
        """
        narrative_hint = None
        if artifacts:
            first = artifacts[0]
            snippet = (first.summary or first.content or "").strip()
            if snippet:
                narrative_hint = snippet.splitlines()[0][:160]

        # Build a compact, claim-first outline within budget lower bound
        seeds: List[dict] = []

        # Title/Context
        seeds.append(
            {
                "title": f"{request.topic}: Why it matters now",
                "message": (f"Audience: {request.audience}. Desired outcome: {request.desired_outcome}."
                            if (request.audience or request.desired_outcome) else None),
                "expected_evidence": ["Context graphic", "Problem statement"],
                "notes": "Open strong with a single-sentence takeaway.",
                "layout": "Title only",
            }
        )

        # Key insights (2–3 slides)
        seeds.append(
            {
                "title": "Insight 1: The most material driver",
                "message": narrative_hint or "Highlight the most impactful observation.",
                "expected_evidence": ["Line chart", "KPI callout"],
                "notes": "Quantify impact; keep claim crisp.",
                "layout": "Single Chart + Bullets",
            }
        )
        seeds.append(
            {
                "title": "Insight 2: Contrast that reframes the decision",
                "message": "Show the before/after or cohort comparison.",
                "expected_evidence": ["Comparison chart"],
                "notes": "Avoid clutter; annotate directly on chart.",
                "layout": "Single chart",
            }
        )

        # Recommendation
        seeds.append(
            {
                "title": "Recommendation: What to do next and why",
                "message": "Tie actions to outcomes; specify owners and timeline.",
                "expected_evidence": ["Checklist", "Timeline"],
                "notes": "Keep to 3 actions max; each action has an owner.",
                "layout": "Two column text",
            }
        )

        # Scale up to min_slides by duplicating insight frames with placeholders if needed
        while len(seeds) < self.min_slides:
            n = len(seeds) - 2  # number insights added so far (roughly)
            seeds.insert(
                -1,
                {
                    "title": f"Insight {n+3}: Supporting angle",
                    "message": "Provide a secondary but decision-relevant lens.",
                    "expected_evidence": ["Bar chart", "Table"],
                    "notes": "Keep consistent visual grammar.",
                    "layout": "Single chart",
                },
            )

        slide_blueprints: List[SlideOutline] = []
        for idx, seed in enumerate(seeds, start=1):
            slide_blueprints.append(
                SlideOutline(
                    slide_id=f"S{idx:02d}",
                    title=seed["title"],
                    message=seed.get("message"),
                    expected_evidence=seed.get("expected_evidence", []) or [],
                    notes=seed.get("notes"),
                    layout=seed.get("layout"),
                )
            )

        return PresentationOutlineResponse(slides=slide_blueprints)

    def _filter_artifacts(self, artifacts: Sequence[OutlineArtifact]) -> List[OutlineArtifact]:
        eligible: List[OutlineArtifact] = []
        skipped: List[str] = []

        for artifact in artifacts or []:
            candidate = artifact.path or artifact.name or ""
            _, ext = os.path.splitext(candidate.lower())
            if ext in self.allowed_artifact_exts:
                eligible.append(artifact)
            else:
                skipped.append(candidate or "<unknown>")

        if skipped:
            log.info("Skipping %d non-text artifacts: %s", len(skipped), ", ".join(skipped[:5]))
        return eligible
