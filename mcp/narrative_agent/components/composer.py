from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, Iterable, List, Optional

from components.models import File, NarrativeArtifact, NarrativeOutput, NarrativeRequest
from aws.s3_client import S3Client
from utils.LLMAdapter import LLMAdapter

logger = logging.getLogger(__name__)

DEFAULT_TEXT_EXTS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".log",
    ".sql",
    ".py",
    ".ipynb",
    ".html",
}

MAX_BYTES_INLINE = 120_000
CHARS_PER_ARTIFACT = 6_000
MAX_ARTIFACT_BYTES = 1_000_000


class NarrativeComposer:
    """
    Generates narratives from artifacts and a user goal.
    """

    def __init__(
        self,
        *,
        s3_client: Optional[S3Client] = None,
        artifact_llm: Optional[LLMAdapter] = None,
        base_tmp_dir: str = "tmp",
        s3_prefix: str = "threads",
        inputs_dirname: str = "inputs",
        outputs_dirname: str = "outputs",
    ) -> None:
        self.s3_client = s3_client
        self.artifact_llm = artifact_llm
        self.base_tmp = pathlib.Path(base_tmp_dir).resolve()
        self.s3_prefix = s3_prefix
        self.inputs_dirname = inputs_dirname
        self.outputs_dirname = outputs_dirname

    # ---------- Paths ----------
    def _thread_dir(self, thread_id: str) -> pathlib.Path:
        d = self.base_tmp / thread_id / "narrative"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _outputs_dir(self, thread_id: str) -> pathlib.Path:
        d = self._thread_dir(thread_id) / self.outputs_dirname
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---------- Artifact ingestion ----------
    def _should_inline(self, file: File) -> bool:
        if file.size and file.size > MAX_BYTES_INLINE:
            return False
        ext = pathlib.Path(file.name).suffix.lower()
        return ext in DEFAULT_TEXT_EXTS

    def _read_artifact_text(self, file: File) -> Optional[str]:
        if not self.s3_client or not file.path.startswith("s3://"):
            return None
        try:
            data, _ = self.s3_client.get_bytes(file.path)
            text = data.decode("utf-8", errors="replace")
            return text[:CHARS_PER_ARTIFACT]
        except Exception as exc:
            logger.warning("Unable to read artifact %s (%s): %s", file.name, file.path, exc)
            return None

    def _guess_file_category(self, filename: str) -> str:
        ext = pathlib.Path(filename).suffix.lower()
        if ext in {".pdf", ".doc", ".docx", ".ppt", ".pptx"}:
            return "document"
        if ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
            return "image"
        if ext in DEFAULT_TEXT_EXTS:
            return "text"
        return "unknown"

    def _artifact_summary_prompt_text(self, user_goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        prompt_lines = [
            f"Goal: {user_goal}",
            "",
            f"File: {context['name']}",
            f"Path: {context.get('path', '')}",
            "",
            "Extract all facts, metrics, and insights that are useful for building a business narrative.",
            "Highlight trends, anomalies, stakeholders, risks, and recommendations mentioned in the file.",
        ]
        if context.get("description"):
            prompt_lines.append(f"Description: {context['description']}")
        if context.get("excerpt"):
            prompt_lines.append("\nBEGIN FILE EXCERPT\n")
            prompt_lines.append(context["excerpt"])
            prompt_lines.append("\nEND FILE EXCERPT\n")
        prompt = "\n".join(prompt_lines)
        return [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                ],
            }
        ]

    def _artifact_summary_prompt_media(
        self,
        user_goal: str,
        context: Dict[str, Any],
        media_type: str,
        media_url: str,
    ) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Goal: {user_goal}\n\n"
                    f"File: {context['name']}\n\n"
                    "Summarise every detail needed for a business narrative. "
                    "Explain what the chart/document shows, covering KPIs, trends, impacts, and recommended actions."
                ),
            }
        ]
        if context.get("description"):
            content.insert(0, {"type": "input_text", "text": f"Description: {context['description']}\n\n"})
        if media_type == "file":
            content.append({"type": "input_file", "file_url": media_url})
        elif media_type == "image":
            content.append({"type": "input_image", "image_url": media_url})
        return [
            {
                "role": "user",
                "content": content,
            }
        ]

    def _summarise_artifacts(
        self,
        user_goal: str,
        artifacts: Iterable[File],
    ) -> List[Dict[str, Any]]:
        contexts: List[Dict[str, Any]] = []
        artifacts_list = list(artifacts)
        for art in artifacts_list:
            entry: Dict[str, Any] = {
                "name": art.name,
                "path": art.path,
                "description": art.description or "",
            }
            if art.size and art.size > MAX_ARTIFACT_BYTES:
                entry["note"] = f"Skipped (file too large: {art.size} bytes)"
                contexts.append(entry)
                continue
            if self._should_inline(art):
                text = self._read_artifact_text(art)
                if text:
                    entry["excerpt"] = text
            contexts.append(entry)

        if not self.artifact_llm:
            return contexts

        enriched: List[Dict[str, Any]] = []
        for entry, art in zip(contexts, artifacts_list):
            ctx = dict(entry)
            if ctx.get("note"):
                enriched.append(ctx)
                continue

            if not self.s3_client or not art.path.startswith("s3://"):
                ctx["summary"] = "Artifact not stored in S3; manual review required."
                enriched.append(ctx)
                continue

            category = self._guess_file_category(art.name)
            try:
                if category == "text":
                    if "excerpt" not in ctx:
                        ctx["note"] = "Unable to inline text for summarisation."
                    else:
                        prompt = self._artifact_summary_prompt_text(user_goal, ctx)
                        summary = self.artifact_llm.response(prompt)
                        ctx["summary"] = summary.strip()
                elif category == "document":
                    url = self.s3_client.presigned_get(art.path, expires_in=3600)
                    prompt = self._artifact_summary_prompt_media(user_goal, ctx, "file", url)
                    summary = self.artifact_llm.response(prompt)
                    ctx["summary"] = summary.strip()
                elif category == "image":
                    url = self.s3_client.presigned_get(art.path, expires_in=3600)
                    prompt = self._artifact_summary_prompt_media(user_goal, ctx, "image", url)
                    summary = self.artifact_llm.response(prompt)
                    ctx["summary"] = summary.strip()
                else:
                    ctx["note"] = "Unsupported artifact type for automated summary."
            except Exception as exc:
                logger.warning("Failed to summarise artifact %s: %s", art.name, exc)
                ctx["note"] = f"Summarisation failed: {exc}"
            enriched.append(ctx)

        return enriched

    def _collect_artifact_context(self, user_goal: str, artifacts: Iterable[File]) -> List[Dict[str, Any]]:
        return self._summarise_artifacts(user_goal, artifacts)

    # ---------- Prompt building ----------
    @staticmethod
    def _build_prompt(
        task: str,
        audience: Optional[str],
        tone: Optional[str],
        contexts: List[Dict[str, str]],
    ) -> List[Dict[str, object]]:
        lines = [
            f"User Goal: {task}",
            "",
        ]
        if audience:
            lines.append(f"Audience: {audience}")
        if tone:
            lines.append(f"Desired Tone: {tone}")
        lines.append("")
        lines.append("Artifact Context:")
        for idx, ctx in enumerate(contexts, 1):
            lines.append(f"{idx}. {ctx['name']} – {ctx.get('description', '')}")
            if ctx.get("path"):
                lines.append(f"   Path: {ctx['path']}")
            if ctx.get("excerpt"):
                excerpt = ctx["excerpt"].strip()
                if excerpt:
                    lines.append("   Excerpt:")
                    lines.append(f"   {excerpt}")
        lines.append("")
        lines.append(
            "Using the artifacts, craft a professional, business-ready narrative. "
            "Deliverables must be strict JSON with keys:\n"
            "{\n"
            '  "narrative_md": "Full narrative in markdown",\n'
            '  "executive_summary_md": "Executive summary markdown (<= 12 bullet points)",\n'
            '  "talking_points_md": "Optional markdown bullet list (<= 6 bullets)",\n'
            '  "references": ["Artifact name -> how it is used in the narrative", ...]\n'
            "}\n"
            "Rules:\n"
            "- Use concise, persuasive business language.\n"
            "- Tie every recommendation to evidence from the artifacts.\n"
            "- Include clear sections: Situation, Insights, Recommendations, Next Steps.\n"
            "- Always cite artifacts in-line using (See: Artifact Name).\n"
            "- If data is limited, explicitly state assumptions.\n"
        )
        prompt_text = "\n".join(lines)
        return [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt_text},
                ],
            }
        ]

    @staticmethod
    def _extract_json(response: str) -> Dict[str, object]:
        if "```" in response:
            start = response.find("```")
            fence = response[start + 3 :]
            # find end
            end = fence.find("```")
            code_block = fence[:end] if end != -1 else fence
            # remove leading language hints
            code_block = code_block.strip()
            if code_block.lower().startswith("json"):
                code_block = code_block[4:].strip()
            response = code_block
        response = response.strip()
        try:
            return json.loads(response)
        except Exception:
            logger.error("Failed to parse narrative JSON: %s", response[:500])
            raise

    def compose(
        self,
        *,
        thread_id: str,
        request: NarrativeRequest,
        narrative_llm: LLMAdapter,
        upload_to_s3: bool = True,
    ) -> NarrativeOutput:
        contexts = self._collect_artifact_context(request.task, request.files_in)
        prompt = self._build_prompt(
            task=request.task,
            audience=request.audience,
            tone=request.tone,
            contexts=contexts,
        )

        response = narrative_llm.response(prompt)
        payload = self._extract_json(response)

        narrative_md = str(payload.get("narrative_md") or "").strip()
        exec_summary_md = str(payload.get("executive_summary_md") or "").strip()
        talking_points_md = str(payload.get("talking_points_md") or "").strip()

        if not narrative_md:
            raise ValueError("Narrative LLM response missing 'narrative_md'")
        if not exec_summary_md:
            raise ValueError("Narrative LLM response missing 'executive_summary_md'")

        artifacts_out: List[Dict[str, Any]] = []
        references = payload.get("references") or []

        outputs_dir = self._outputs_dir(thread_id)
        narrative_path = outputs_dir / "narrative.md"
        exec_summary_path = outputs_dir / "executive_summary.md"
        narrative_path.write_text(narrative_md, encoding="utf-8")
        exec_summary_path.write_text(exec_summary_md, encoding="utf-8")

        uploaded_artifacts: List[NarrativeOutput] = []
        narrative_bytes = narrative_md.encode("utf-8")
        summary_bytes = exec_summary_md.encode("utf-8")

        if upload_to_s3 and self.s3_client:
            base_key = f"{self.s3_prefix}/{thread_id}/narrative"
            narrative_key = f"{base_key}/narrative.md"
            summary_key = f"{base_key}/executive_summary.md"

            self.s3_client.put_bytes(
                narrative_key,
                narrative_bytes,
                content_type="text/markdown",
            )
            self.s3_client.put_bytes(
                summary_key,
                summary_bytes,
                content_type="text/markdown",
            )

            artifacts_out.extend(
                [
                    {
                        "name": "narrative.md",
                        "path": f"s3://{self.s3_client.bucket}/{narrative_key}",
                        "description": "Full narrative in markdown format.",
                        "size": len(narrative_bytes),
                    },
                    {
                        "name": "executive_summary.md",
                        "path": f"s3://{self.s3_client.bucket}/{summary_key}",
                        "description": "Executive summary for leadership.",
                        "size": len(summary_bytes),
                    },
                ]
            )
        else:
            artifacts_out.extend(
                [
                    {
                        "name": "narrative.md",
                        "path": str(narrative_path),
                        "description": "Full narrative in markdown format.",
                        "size": len(narrative_bytes),
                    },
                    {
                        "name": "executive_summary.md",
                        "path": str(exec_summary_path),
                        "description": "Executive summary for leadership.",
                        "size": len(summary_bytes),
                    },
                ]
            )

        if talking_points_md:
            talking_points_path = outputs_dir / "talking_points.md"
            talking_points_path.write_text(talking_points_md, encoding="utf-8")
            talking_points_bytes = talking_points_md.encode("utf-8")
            if upload_to_s3 and self.s3_client:
                tp_key = f"{self.s3_prefix}/{thread_id}/narrative/talking_points.md"
                self.s3_client.put_bytes(
                    tp_key,
                    talking_points_bytes,
                    content_type="text/markdown",
                )
                artifacts_out.append(
                    {
                        "name": "talking_points.md",
                        "path": f"s3://{self.s3_client.bucket}/{tp_key}",
                        "description": "Optional talking points derived from the narrative.",
                        "size": len(talking_points_bytes),
                    }
                )
            else:
                artifacts_out.append(
                    {
                        "name": "talking_points.md",
                        "path": str(talking_points_path),
                        "description": "Optional talking points derived from the narrative.",
                        "size": len(talking_points_bytes),
                    }
                )

        # attach references if available
        if isinstance(references, list):
            for idx, ref in enumerate(references, 1):
                if isinstance(ref, str):
                    artifacts_out.append(
                        {
                            "name": f"reference_{idx}",
                            "path": "",
                            "description": ref,
                        }
                    )

        narrative_output = NarrativeOutput(
            narrative_md=narrative_md,
            executive_summary_md=exec_summary_md,
            talking_points_md=talking_points_md or None,
            artifacts=[NarrativeArtifact(**a) for a in artifacts_out],
        )
        return narrative_output
