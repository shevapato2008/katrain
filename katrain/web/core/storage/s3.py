"""S3-compatible storage backend (MinIO in phase 1 ≡ Aliyun OSS in phase 2).

``is_remote = True`` → the app 302-redirects clients to ``public_url`` so video
bytes never traverse FastAPI. The same class targets MinIO and OSS; only
endpoint / credentials / public-base-url differ (config, not code).

Key design points (see superpowers/tracks/tutorial-database/plan.md):
* path-style addressing — required by MinIO, harmless for OSS;
* uploads carry ``Content-Type`` + ``Cache-Control: ...immutable`` so the CDN /
  browser cache long-lives them;
* ``public_url`` returns ``S3_PUBLIC_BASE_URL/<key>`` (public-read bucket, D7),
  or a presigned URL when ``use_presigned`` is set (private bucket).
"""
from __future__ import annotations

import mimetypes

from katrain.web.core.storage.base import PutData, StorageBackend, normalize_key

CACHE_CONTROL = "public, max-age=31536000, immutable"
DEFAULT_CONTENT_TYPE = "application/octet-stream"


class S3StorageBackend(StorageBackend):
    is_remote = True

    def __init__(
        self,
        *,
        bucket: str | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        public_base_url: str | None = None,
        use_presigned: bool | None = None,
        presign_ttl_sec: int | None = None,
    ):
        # Lazy-read settings so callers may override per-arg (tests) or rely on config.
        from katrain.web.core.config import settings

        self._bucket = bucket or settings.S3_BUCKET
        self._endpoint_url = endpoint_url if endpoint_url is not None else (settings.S3_ENDPOINT_URL or None)
        self._region = region if region is not None else (settings.S3_REGION or None)
        self._public_base_url = (
            public_base_url if public_base_url is not None else settings.S3_PUBLIC_BASE_URL
        ).rstrip("/")
        self._use_presigned = settings.S3_USE_PRESIGNED if use_presigned is None else use_presigned
        self._presign_ttl = settings.S3_PRESIGN_TTL_SEC if presign_ttl_sec is None else presign_ttl_sec

        access_key = access_key if access_key is not None else (settings.S3_ACCESS_KEY or None)
        secret_key = secret_key if secret_key is not None else (settings.S3_SECRET_KEY or None)

        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            region_name=self._region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            # path-style is required by MinIO; harmless for OSS.
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
        )

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _content_type(key: str, explicit: str | None) -> str:
        if explicit:
            return explicit
        return mimetypes.guess_type(key)[0] or DEFAULT_CONTENT_TYPE

    def _head(self, key: str):
        import botocore.exceptions

        try:
            return self._client.head_object(Bucket=self._bucket, Key=key)
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise FileNotFoundError(key) from e
            raise

    # ── contract ───────────────────────────────────────────────────────────
    def put(self, key: str, data: PutData, *, content_type: str | None = None) -> None:
        key = normalize_key(key)
        body = bytes(data) if isinstance(data, (bytes, bytearray)) else data
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=self._content_type(key, content_type),
            CacheControl=CACHE_CONTROL,
        )

    def exists(self, key: str) -> bool:
        try:
            self._head(normalize_key(key))
            return True
        except FileNotFoundError:
            return False

    def size(self, key: str) -> int:
        return self._head(normalize_key(key))["ContentLength"]

    def read(self, key: str) -> bytes:
        import botocore.exceptions

        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=normalize_key(key))
        except botocore.exceptions.ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise FileNotFoundError(key) from e
            raise
        return obj["Body"].read()

    def read_range(self, key: str, start: int, length: int) -> bytes:
        end = start + length - 1
        obj = self._client.get_object(
            Bucket=self._bucket, Key=normalize_key(key), Range=f"bytes={start}-{end}"
        )
        return obj["Body"].read()

    def public_url(self, key: str) -> str:
        key = normalize_key(key)
        if self._use_presigned:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=self._presign_ttl,
            )
        return f"{self._public_base_url}/{key}"
