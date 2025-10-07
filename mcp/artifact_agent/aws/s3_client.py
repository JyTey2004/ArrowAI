# app/aws/s3_client.py
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
    def parse_s3_uri(uri: str) -> Tuple[str, str]:
        if not uri.startswith("s3://"):
            raise ValueError(f"Not an s3 URI: {uri}")
        _, rest = uri.split("s3://", 1)
        bucket, key = rest.split("/", 1)
        return bucket, key

    def _resolve_bucket_key(self, key_or_uri: str) -> Tuple[str, str]:
        if key_or_uri.startswith("s3://"):
            bucket, key = self.parse_s3_uri(key_or_uri)
            return bucket, key
        return self.bucket, key_or_uri

    # ---------------------------
    # Bucket utilities (optional)
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
        bucket, resolved_key = self._resolve_bucket_key(key)
        kwargs = {"Bucket": bucket, "Key": resolved_key}
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
        bucket, resolved_prefix = self._resolve_bucket_key(prefix)
        kwargs = {
            "Bucket": bucket,
            "Prefix": resolved_prefix,
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
        bucket, resolved_key = self._resolve_bucket_key(key)
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

        resp = self.s3.put_object(Bucket=bucket, Key=resolved_key, Body=data, **extra)
        head = self.head_object(key, resp.get("VersionId"))
        return self._manifest_from_head(bucket, resolved_key, head, override_sha=sha)

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
        bucket, resolved_key = self._resolve_bucket_key(key)
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

        self.s3.upload_file(local_path, bucket, resolved_key, ExtraArgs=extra_args)
        head = self.head_object(key)
        return self._manifest_from_head(bucket, resolved_key, head, override_sha=sha)

    # ---------------------------
    # Downloads
    # ---------------------------
    def get_bytes(self, key: str, version_id: str | None = None, byte_range: Tuple[int, int] | None = None) -> Tuple[bytes, Dict[str, Any]]:
        bucket, resolved_key = self._resolve_bucket_key(key)
        kwargs = {"Bucket": bucket, "Key": resolved_key}
        if version_id:
            kwargs["VersionId"] = version_id
        if byte_range:
            start, end = byte_range
            kwargs["Range"] = f"bytes={start}-{end}"
        obj = self.s3.get_object(**kwargs)
        data = obj["Body"].read()
        return data, obj

    def download_file(self, key: str, local_path: str, version_id: str | None = None) -> None:
        bucket, resolved_key = self._resolve_bucket_key(key)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        extra: Dict[str, Any] = {}
        if version_id:
            extra["VersionId"] = version_id
        logger.info(f"Downloading s3://{bucket}/{resolved_key} to {local_path}")
        self.s3.download_file(bucket, resolved_key, local_path, ExtraArgs=extra or None)

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
        bucket, resolved_key = self._resolve_bucket_key(key)
        params: Dict[str, Any] = {"Bucket": bucket, "Key": resolved_key}
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
        content_type: str | None = None,
        acl: str | None = None,
        sse: str | None = None,
        kms_key_id: str | None = None,
        metadata: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        bucket, resolved_key = self._resolve_bucket_key(key)
        params: Dict[str, Any] = {"Bucket": bucket, "Key": resolved_key}
        if content_type:
            params["ContentType"] = content_type
        if acl:
            params["ACL"] = acl
        if sse:
            params["ServerSideEncryption"] = sse
        if kms_key_id:
            params["SSEKMSKeyId"] = kms_key_id
        if metadata:
            params["Metadata"] = metadata
        url = self.s3.generate_presigned_url("put_object", Params=params, ExpiresIn=expires_in)
        return {"url": url, "method": "PUT", "headers": {}, "key": resolved_key, "bucket": bucket}

    # ---------------------------
    # Copy / Delete
    # ---------------------------
    def copy(self, source_key: str, dest_key: str, source_version_id: str | None = None, metadata_directive: str = "COPY") -> S3Manifest:
        source_bucket, source_resolved = self._resolve_bucket_key(source_key)
        dest_bucket, dest_resolved = self._resolve_bucket_key(dest_key)
        copy_source = {"Bucket": source_bucket, "Key": source_resolved}
        if source_version_id:
            copy_source["VersionId"] = source_version_id
        resp = self.s3.copy_object(
            Bucket=dest_bucket,
            Key=dest_resolved,
            CopySource=copy_source,
            MetadataDirective=metadata_directive,
        )
        head = self.head_object(dest_key, resp.get("VersionId"))
        return self._manifest_from_head(dest_bucket, dest_resolved, head, override_sha=None)

    def delete_object(self, key: str, version_id: str | None = None) -> Dict[str, Any]:
        bucket, resolved_key = self._resolve_bucket_key(key)
        kwargs = {"Bucket": bucket, "Key": resolved_key}
        if version_id:
            kwargs["VersionId"] = version_id
        return self.s3.delete_object(**kwargs)

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        token = None
        while True:
            resp = self.list(prefix, limit=1000, continuation_token=token)
            contents = resp.get("Contents", [])
            if not contents:
                break
            to_delete = [{"Key": c["Key"]} for c in contents]
            out = self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": to_delete, "Quiet": True})
            deleted += len(out.get("Deleted", []))
            token = resp.get("NextContinuationToken")
            if not token:
                break
        return deleted

    # ---------------------------
    # Manifests
    # ---------------------------
    def _manifest_from_head(self, bucket: str, key: str, head: Dict[str, Any], override_sha: Optional[str]) -> S3Manifest:
        size = head.get("ContentLength", 0)
        etag = head.get("ETag", "").strip('"')
        version_id = head.get("VersionId")
        ctype = head.get("ContentType")
        meta = head.get("Metadata", {}) or {}
        sha256_val = override_sha or meta.get("sha256")
        return S3Manifest(
            bucket=bucket,
            key=key,
            uri=f"s3://{bucket}/{key}",
            size=size,
            etag=etag,
            version_id=version_id,
            content_type=ctype,
            sha256=sha256_val,
            metadata=meta,
        )

    # ---------------------------
    # Convenience: JSON helpers
    # ---------------------------
    def put_json(self, key: str, obj: Any, **kwargs) -> S3Manifest:
        data = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self.put_bytes(key, data, content_type="application/json", **kwargs)

    def get_json(self, key: str, version_id: str | None = None) -> Any:
        data, _ = self.get_bytes(key, version_id)
        return json.loads(data.decode("utf-8"))

