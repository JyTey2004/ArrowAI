from __future__ import annotations

import logging
import pathlib
import re
from typing import Optional, Tuple

from aws.s3_client import S3Client
from components.reader import ArtifactReader
from components.models import ArtifactSpec

logger = logging.getLogger(__name__)

JSON_BLOCK = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
ANY_BLOCK = re.compile(r"```\s*\n(.*?)\n```", re.DOTALL)

TEXT_FILE_TYPES = {"txt", "log", "md", "markdown", "json", "yaml", "yml", "csv", "tsv"}
RICH_FILE_TYPES = {"pdf", "docx", "pptx"}
IMAGE_FILE_TYPES = {"png", "jpg", "jpeg", "gif", "bmp", "webp"}
SPREADSHEET_TYPES = {"xlsx", "xls"}


class ArtifactLogManager:
    def __init__(
        self,
        *,
        reader: ArtifactReader,
        s3_client: S3Client,
        summary_llm,
        base_tmp_dir: str = "tmp",
        presign_ttl: int = 3600,
        max_inline_bytes: int = 64_000,
    ) -> None:
        self.reader = reader
        self.s3_client = s3_client
        self.summary_llm = summary_llm
        self.base_tmp = pathlib.Path(base_tmp_dir).resolve()
        self.presign_ttl = presign_ttl
        self.max_inline_bytes = max_inline_bytes

    # ---------- paths ----------
    def _artifacts_dir(self, thread_id: str) -> pathlib.Path:
        return self.base_tmp / thread_id

    def artifacts_log_path(self, thread_id: str) -> pathlib.Path:
        return self._artifacts_dir(thread_id) / "ARTIFACTS.md"

    # ---------- logging helpers ----------
    def _artifacts_log_info(self, thread_id: str) -> str:
        logf = self.artifacts_log_path(thread_id)
        if logf.exists():
            return logf.read_text(encoding="utf-8", errors="ignore")
        return ""

    def _append_artifacts_log(self, thread_id: str, text: str) -> None:
        logf = self.artifacts_log_path(thread_id)
        logf.parent.mkdir(parents=True, exist_ok=True)
        header = "# Artifacts Log\n\n"
        prev = logf.read_text(encoding="utf-8", errors="ignore") if logf.exists() else header
        logf.write_text(prev + text + "\n", encoding="utf-8")

    # ---------- file helpers ----------
    @staticmethod
    def guess_file_type(filename: str) -> str:
        if "." not in filename:
            return "unknown"
        return filename.lower().rsplit(".", 1)[-1]

    def _extract_markdown(self, output: str) -> str:
        if "```" not in output:
            return output.strip()
        m = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", output, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return output.replace("```markdown", "").replace("```", "").strip()

    # ---------- prompts ----------
    @staticmethod
    def _rich_prompt(user_goal: str, filename: str, description: Optional[str], file_url: str, file_type: str):
        base_prompt = {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        f"Goal: {user_goal}\n\n"
                        f"Output all relevant information from {filename}, in a markdown bullet list without quotes."
                    ),
                },
            ],
        }
        if description:
            base_prompt["content"].insert(1, {"type": "input_text", "text": f"File description: {description}\n\n"})

        if file_type in RICH_FILE_TYPES:
            base_prompt["content"].append({"type": "input_file", "file_url": file_url})
        elif file_type in IMAGE_FILE_TYPES:
            base_prompt["content"].append({"type": "input_image", "image_url": file_url})
        return [base_prompt]

    @staticmethod
    def _text_prompt(user_goal: str, filename: str, content: str) -> list[dict]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Goal: {user_goal}\n\n"
                            f"File: {filename}\n\n"
                            "Output all relevant information from the file, in a markdown bullet list without quotes.\n\n"
                            f"BEGIN FILE CONTENT\n{content}\nEND FILE CONTENT"
                        ),
                    }
                ],
            }
        ]

    # ---------- main API ----------
    def already_logged(self, thread_id: str, artifact_name: str) -> bool:
        all_info = self._artifacts_log_info(thread_id)
        needle = f"**{artifact_name}:**"
        return needle in all_info

    def log_skip(self, thread_id: str, artifact: ArtifactSpec, reason: str) -> Tuple[str, str]:
        entry = f"- **{artifact.name}:** \n  - Skipped ({reason})\n\n"
        self._append_artifacts_log(thread_id, entry)
        return entry, reason

    def summarize_text_artifact(
        self,
        *,
        thread_id: str,
        user_goal: str,
        artifact: ArtifactSpec,
        max_bytes: Optional[int] = None,
    ) -> Tuple[str, str, bool, Optional[str]]:
        fetch_limit = max_bytes or self.max_inline_bytes
        info = self.reader.fetch_text(
            path=artifact.path,
            name=artifact.name,
            max_bytes=fetch_limit,
            include_presigned_url=True,
        )
        if info.get("binary"):
            raise ValueError("Artifact detected as binary when expecting text.")

        prompt = self._text_prompt(user_goal, artifact.name, info["text"])
        result = self.summary_llm.response(prompt)
        summary = self._extract_markdown(result)

        entry = f"### **{artifact.name}:** \n{summary}\n"
        self._append_artifacts_log(thread_id, entry)
        return entry, summary, info.get("truncated", False), info.get("presigned_url")

    def summarize_rich_artifact(
        self,
        *,
        thread_id: str,
        user_goal: str,
        artifact: ArtifactSpec,
        file_type: str,
    ) -> Tuple[str, str, str]:
        url = self.s3_client.presigned_get(artifact.path, expires_in=self.presign_ttl)
        prompt = self._rich_prompt(user_goal, artifact.name, artifact.description, url, file_type)
        result = self.summary_llm.response(prompt)
        summary = self._extract_markdown(result)
        entry = f"### **{artifact.name}:** \n{summary}\n"
        self._append_artifacts_log(thread_id, entry)
        return entry, summary, url
