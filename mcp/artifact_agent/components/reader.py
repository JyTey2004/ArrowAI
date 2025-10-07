from __future__ import annotations

import logging
import os
from typing import Dict, Optional, Tuple

from aws.s3_client import S3Client

logger = logging.getLogger(__name__)

TEXTUAL_MIME_PREFIXES = ("text/", "application/json", "application/xml")
TEXTUAL_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".log",
    ".py",
    ".ipynb",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sql",
    ".ini",
    ".cfg",
    ".env",
}


def _extract_charset(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return None
    parts = content_type.split(";")
    for part in parts[1:]:
        if "charset=" in part:
            return part.split("charset=", 1)[1].strip()
    return None


class ArtifactReader:
    """Utility that fetches textual previews for artifacts stored in S3."""

    def __init__(
        self,
        s3_client: S3Client,
        *,
        default_max_bytes: int = 32_000,
        hard_max_bytes: int = 200_000,
        presign_ttl: int = 3600,
    ) -> None:
        self.s3_client = s3_client
        self.default_max_bytes = default_max_bytes
        self.hard_max_bytes = hard_max_bytes
        self.presign_ttl = presign_ttl

    def _normalise_limit(self, requested: Optional[int]) -> int:
        limit = requested or self.default_max_bytes
        limit = max(1024, limit)
        limit = min(limit, self.hard_max_bytes)
        return limit

    @staticmethod
    def _looks_textual(name: str, content_type: Optional[str]) -> bool:
        if content_type:
            lowered = content_type.lower()
            if any(lowered.startswith(prefix) for prefix in TEXTUAL_MIME_PREFIXES):
                return True
        ext = os.path.splitext(name)[1].lower()
        return ext in TEXTUAL_EXTENSIONS

    @staticmethod
    def _decode_bytes(data: bytes, preferred_encoding: Optional[str]) -> Tuple[str, str, bool]:
        attempted = []
        candidates = [preferred_encoding, "utf-8", "utf-16", "latin-1"]
        for enc in [c for c in candidates if c]:
            try:
                text = data.decode(enc)
                return text, enc, False
            except UnicodeDecodeError:
                attempted.append(enc)
        # fallback with replacement characters
        fallback_encoding = preferred_encoding or "utf-8"
        text = data.decode(fallback_encoding, errors="replace")
        return text, fallback_encoding, True

    def fetch_text(
        self,
        *,
        path: str,
        name: Optional[str] = None,
        max_bytes: Optional[int] = None,
        encoding: Optional[str] = None,
        include_presigned_url: bool = True,
    ) -> Dict[str, object]:
        resolved_name = name or path.rstrip("/").split("/")[-1]
        limit = self._normalise_limit(max_bytes)

        head = self.s3_client.head_object(path)
        size = head.get("ContentLength", 0)
        content_type = head.get("ContentType")
        metadata = head.get("Metadata", {}) or {}
        etag = head.get("ETag", "").strip('"')
        version_id = head.get("VersionId")
        preferred_encoding = encoding or _extract_charset(content_type)

        looks_text = self._looks_textual(resolved_name, content_type)

        byte_range: Optional[Tuple[int, int]] = None
        if size and size > limit:
            byte_range = (0, limit - 1)

        data, obj = self.s3_client.get_bytes(path, byte_range=byte_range)
        actual_size = len(data)
        truncated = bool(size and actual_size < size)

        if not looks_text:
            presigned_url = None
            if include_presigned_url:
                try:
                    presigned_url = self.s3_client.presigned_get(path, expires_in=self.presign_ttl, version_id=version_id)
                except Exception as exc:
                    logger.warning("Failed to generate presigned URL for %s: %s", path, exc)
            return {
                "name": resolved_name,
                "path": path,
                "size": size,
                "content_type": content_type,
                "binary": True,
                "message": "File appears to be binary; download via presigned_url.",
                "presigned_url": presigned_url,
                "etag": etag,
                "version_id": version_id,
                "metadata": metadata,
            }

        detected_encoding = preferred_encoding

        if not detected_encoding:
            detected_encoding = obj.get("ContentType") and _extract_charset(obj.get("ContentType"))

        text, used_encoding, had_errors = self._decode_bytes(data, detected_encoding)

        presigned_url = None
        if include_presigned_url:
            try:
                presigned_url = self.s3_client.presigned_get(path, expires_in=self.presign_ttl, version_id=version_id)
            except Exception as exc:
                logger.warning("Failed to generate presigned URL for %s: %s", path, exc)

        if truncated:
            text += f"\n\n… TRUNCATED (first {actual_size} bytes of {size} total) …"

        return {
            "name": resolved_name,
            "path": path,
            "size": size,
            "content_type": content_type,
            "encoding": used_encoding,
            "text": text,
            "truncated": truncated,
            "decode_errors": had_errors,
            "presigned_url": presigned_url,
            "etag": etag,
            "version_id": version_id,
            "metadata": metadata,
        }
