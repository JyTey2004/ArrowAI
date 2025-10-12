# presentation_agent/aws/s3_client.py
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

import logging
logger = logging.getLogger(__name__)


@dataclass
class S3Manifest:
    bucket: str
    key: str
    uri: str
    size: int
    etag: str
    version_id: Optional[str]
    content_type: Optional[str]
    sha256: Optional[str]
    metadata: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bucket": self.bucket,
            "key": self.key,
            "uri": self.uri,
            "size": self.size,
            "etag": self.etag,
            "versionId": self.version_id,
            "content_type": self.content_type,
            "sha256": self.sha256,
            "metadata": self.metadata,
        }


class S3Client:
    def __init__(
        self,
        bucket_name: str,
        region_name: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        max_pool_connections: int = 50,
        signature_version: str = "s3v4",
    ):
        self.bucket = bucket_name
        self.s3 = boto3.client(
            "s3",
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            config=Config(
                s3={"addressing_style": "virtual"},
                signature_version=signature_version,
                retries={"max_attempts": 8, "mode": "standard"},
                max_pool_connections=max_pool_connections,
            ),
        )
        self._region = region_name
        logger.info(f"S3Client initialized for bucket '{bucket_name}'")

    # ---------------------------
    # Helpers
    # ---------------------------
    @staticmethod
    def _guess_mime(path_or_name: str, fallback: str = "application/octet-stream") -> str:
        ctype, _ = mimetypes.guess_type(path_or_name)
        return ctype or fallback

    @staticmethod
    def _sha256_file(path: str, bufsize: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(bufsize), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _sha256_bytes(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    def _uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    @staticmethod
    def parse_s3_uri(uri: str) -> str:
        assert uri.startswith("s3://"), f"Not an s3 URI: {uri}"
        _, rest = uri.split("s3://", 1)
        _, key = rest.split("/", 1)
        return key

    # ---------------------------
    # Bucket utilities
    # ---------------------------
    def ensure_bucket(self, create_if_missing: bool = False) -> bool:
        try:
            self.s3.head_bucket(Bucket=self.bucket)
            return True
        except ClientError as e:
            code = int(e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
            if create_if_missing and code in (404, 301, 400):
                kwargs = {"Bucket": self.bucket}
                if self._region and self._region != "us-east-1":
                    kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
                self.s3.create_bucket(**kwargs)
                logger.info(f"Created bucket '{self.bucket}' in region '{self._region}'")
                return True
            logger.error(f"Bucket check failed: {e}")
            return False

    # ---------------------------
    # Core object operations
    # ---------------------------
    def head_object(self, key: str, version_id: str | None = None) -> Dict[str, Any]:
        kwargs = {"Bucket": self.bucket, "Key": key}
        if version_id:
            kwargs["VersionId"] = version_id
        return self.s3.head_object(**kwargs)

    def exists(self, key: str, version_id: str | None = None) -> bool:
        try:
            self.head_object(key, version_id)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def list(self, prefix: str, limit: int = 1000, continuation_token: str | None = None) -> Dict[str, Any]:
        kwargs = {
            "Bucket": self.bucket,
            "Prefix": prefix,
            "MaxKeys": min(max(limit, 1), 1000),
        }
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        return self.s3.list_objects_v2(**kwargs)

    # ---------------------------
    # Uploads
    # ---------------------------
    def put_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
        metadata: Dict[str, str] | None = None,
        cache_control: str | None = None,
        acl: str | None = None,
        sse: str | None = None,
        kms_key_id: str | None = None,
    ) -> S3Manifest:
        if content_type is None:
            content_type = "application/octet-stream"
        sha = self._sha256_bytes(data)
        extra: Dict[str, Any] = {"ContentType": content_type, "Metadata": (metadata or {}) | {"sha256": sha}}
        if cache_control:
            extra["CacheControl"] = cache_control
        if acl:
            extra["ACL"] = acl
        if sse:
            extra["ServerSideEncryption"] = sse
        if kms_key_id:
            extra["SSEKMSKeyId"] = kms_key_id

        resp = self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        head = self.head_object(key, resp.get("VersionId"))
        return self._manifest_from_head(key, head, override_sha=sha)

    def put_file(
        self,
        local_path: str,
        key: str,
        content_type: str | None = None,
        metadata: Dict[str, str] | None = None,
        cache_control: str | None = None,
        acl: str | None = None,
        sse: str | None = None,
        kms_key_id: str | None = None,
        compute_sha256: bool = True,
    ) -> S3Manifest:
        if content_type is None:
            content_type = self._guess_mime(local_path)
        sha = self._sha256_file(local_path) if compute_sha256 else None

        extra_args: Dict[str, Any] = {"ContentType": content_type, "Metadata": metadata or {}}
        if sha:
            extra_args["Metadata"]["sha256"] = sha
        if cache_control:
            extra_args["CacheControl"] = cache_control
        if acl:
            extra_args["ACL"] = acl
        if sse:
            extra_args["ServerSideEncryption"] = sse
        if kms_key_id:
            extra_args["SSEKMSKeyId"] = kms_key_id

        self.s3.upload_file(local_path, self.bucket, key, ExtraArgs=extra_args)
        head = self.head_object(key)
        return self._manifest_from_head(key, head, override_sha=sha)

    # ---------------------------
    # Downloads
    # ---------------------------
    def get_bytes(self, key: str, version_id: str | None = None) -> Tuple[bytes, Dict[str, Any]]:
        parsed_key = self.parse_s3_uri(key) if key.startswith("s3://") else key
        kwargs = {"Bucket": self.bucket, "Key": parsed_key}
        if version_id:
            kwargs["VersionId"] = version_id
        obj = self.s3.get_object(**kwargs)
        data = obj["Body"].read()
        return data, obj

    def download_file(self, key: str, local_path: str, version_id: str | None = None) -> None:
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        extra = {}
        if version_id:
            extra["VersionId"] = version_id
        parsed_key = self.parse_s3_uri(key) if key.startswith("s3://") else key
        logger.info(f"Downloading s3://{self.bucket}/{parsed_key} to {local_path}")
        self.s3.download_file(self.bucket, parsed_key, local_path, ExtraArgs=extra or None)

    # ---------------------------
    # Presigned URLs
    # ---------------------------
    def presigned_get(
        self,
        key: str,
        expires_in: int = 900,
        version_id: str | None = None,
        response_content_type: str | None = None,
        response_content_disposition: str | None = None,
    ) -> str:
        parsed_key = self.parse_s3_uri(key) if key.startswith("s3://") else key
        params: Dict[str, Any] = {"Bucket": self.bucket, "Key": parsed_key}
        if version_id:
            params["VersionId"] = version_id
        if response_content_type:
            params["ResponseContentType"] = response_content_type
        if response_content_disposition:
            params["ResponseContentDisposition"] = response_content_disposition
        return self.s3.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)

    def presigned_put(
        self,
        key: str,
        expires_in: int = 900,
        version_id: str | None = None,
        content_type: str | None = None,
        content_disposition: str | None = None,
    ) -> str:
        parsed_key = self.parse_s3_uri(key) if key.startswith("s3://") else key
        params: Dict[str, Any] = {"Bucket": self.bucket, "Key": parsed_key}
        if version_id:
            params["VersionId"] = version_id
        if content_type:
            params["ContentType"] = content_type
        if content_disposition:
            params["ContentDisposition"] = content_disposition
        return self.s3.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_in)

    # ---------------------------
    # Object manifests
    # ---------------------------
    def _manifest_from_head(
        self,
        key: str,
        head: Dict[str, Any],
        override_sha: Optional[str] = None,
    ) -> S3Manifest:
        md = head.get("Metadata") or {}
        user_meta = md.copy()
        sha = override_sha or md.get("sha256")
        etag = head.get("ETag", "").strip("\"")
        return S3Manifest(
            bucket=self.bucket,
            key=key,
            uri=self._uri(key),
            size=head.get("ContentLength") or 0,
            etag=etag,
            version_id=head.get("VersionId"),
            content_type=head.get("ContentType"),
            sha256=sha,
            metadata=user_meta,
        )

    # ---------------------------
    # JSON helpers
    # ---------------------------
    def put_json(
        self,
        key: str,
        payload: Dict[str, Any],
        content_type: str = "application/json",
        metadata: Optional[Dict[str, str]] = None,
    ) -> S3Manifest:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self.put_bytes(key, data, content_type=content_type, metadata=metadata)

    def get_json(self, key: str, version_id: str | None = None) -> Dict[str, Any]:
        data, _ = self.get_bytes(key, version_id=version_id)
        return json.loads(data.decode("utf-8"))

