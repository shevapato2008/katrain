"""Golden-image artifact library: read manifests from a private bucket, never upload or delete.

Layout (written by smartbox provisioning): `<board>/<version>/manifest.json` next to the image file
it names. The admin console lists manifests, checks each named file exists with the declared size,
keeps a release status in the database, and hands out short-lived signed download links. The
credentials here should be read-only on this bucket.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

MANIFEST = "manifest.json"
MAX_MANIFESTS = 500
MAX_MANIFEST_BYTES = 64 * 1024
LINK_TTL_S = 12 * 3600
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")


@dataclass(frozen=True)
class ArtifactConfig:
    endpoint: str
    public_endpoint: str
    bucket: str
    access_key: str
    secret_key: str


def load_config() -> ArtifactConfig | None:
    endpoint = os.getenv("KATRAIN_ARTIFACTS_S3_ENDPOINT", "").strip()
    access, secret = os.getenv("KATRAIN_ARTIFACTS_ACCESS_KEY", ""), os.getenv("KATRAIN_ARTIFACTS_SECRET_KEY", "")
    if not (endpoint and access and secret):
        return None
    return ArtifactConfig(
        endpoint=endpoint,
        public_endpoint=os.getenv("KATRAIN_ARTIFACTS_PUBLIC_ENDPOINT", "").strip() or endpoint,
        bucket=os.getenv("KATRAIN_ARTIFACTS_BUCKET", "golden-images").strip() or "golden-images",
        access_key=access,
        secret_key=secret,
    )


def client(config: ArtifactConfig, public: bool = False):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=config.public_endpoint if public else config.endpoint,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4", connect_timeout=3, read_timeout=10, retries={"max_attempts": 1}),
    )


def validate(manifest: dict) -> list[str]:
    problems = []
    for key in ("version", "board", "file", "sha256", "size", "uploaded_by", "uploaded_at"):
        if key not in manifest:
            problems.append(f"缺少字段 {key}")
    if "file" in manifest and not (isinstance(manifest["file"], str) and _FILE.match(manifest["file"])):
        problems.append("file 必须是同目录下的文件名")
    if "sha256" in manifest and not (isinstance(manifest["sha256"], str) and _SHA256.match(manifest["sha256"])):
        problems.append("sha256 格式不对")
    if "size" in manifest and not (isinstance(manifest["size"], int) and manifest["size"] > 0):
        problems.append("size 必须是正整数")
    return problems


def list_images(config: ArtifactConfig, s3=None) -> dict:
    """Every manifest in the bucket, each with its problems (never silently skipped)."""
    s3 = s3 or client(config)
    keys, truncated = [], False
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=config.bucket):
        for item in page.get("Contents", []):
            if item["Key"].endswith("/" + MANIFEST):
                keys.append(item["Key"])
                if len(keys) >= MAX_MANIFESTS:
                    truncated = True
                    break
        if truncated:
            break
    images = []
    for key in sorted(keys):
        prefix = key[: -len(MANIFEST)]
        entry = {"prefix": prefix, "manifest": None, "problems": [], "object_size": None}
        try:
            head = s3.head_object(Bucket=config.bucket, Key=key)
            if head["ContentLength"] > MAX_MANIFEST_BYTES:
                raise ValueError("manifest 超过 64 KB")
            manifest = json.loads(s3.get_object(Bucket=config.bucket, Key=key)["Body"].read())
            if not isinstance(manifest, dict):
                raise ValueError("manifest 不是 JSON 对象")
            entry["manifest"] = {k: manifest.get(k) for k in ("version", "board", "file", "sha256", "size", "uploaded_by", "uploaded_at", "notes")}
            entry["problems"] = validate(manifest)
            if not entry["problems"]:
                try:
                    obj = s3.head_object(Bucket=config.bucket, Key=prefix + manifest["file"])
                    entry["object_size"] = obj["ContentLength"]
                    if obj["ContentLength"] != manifest["size"]:
                        entry["problems"].append("文件大小与 manifest 不符")
                except Exception:
                    entry["problems"].append("manifest 指向的文件不存在")
        except Exception as exc:
            entry["problems"].append(f"manifest 无法读取：{exc}" if isinstance(exc, ValueError) else "manifest 无法读取")
        images.append(entry)
    return {"images": images, "truncated": truncated}


def signed_link(config: ArtifactConfig, key: str, s3=None) -> str:
    s3 = s3 or client(config, public=True)
    return s3.generate_presigned_url("get_object", Params={"Bucket": config.bucket, "Key": key}, ExpiresIn=LINK_TTL_S)
