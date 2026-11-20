"""Publish the approved OGS release to live PROD storage, manifest last.

Run inside the existing PROD web container with its storage configuration.
Only new keys in the fixed release prefix may be created; old releases remain intact.
"""

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

from botocore.exceptions import ClientError
from sqlalchemy import text

from katrain.web.core.db import SessionLocal
from katrain.web.core.storage import get_storage_backend


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--publish", action="store_true", help="without this flag only validate the release")
    parser.add_argument("--workers", type=int, choices=(6, 12, 24), default=6)
    parser.add_argument("--source-root", type=Path, help="optional verified source cache, keyed by release object path")
    args = parser.parse_args()
    index = json.loads((args.bundle / "release-index.json").read_text())
    manifest_bytes = (args.bundle / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert index["release_id"] == manifest["release_id"] == "ogs-full-20261117"
    assert index["prefix"] == "tutorial_demos/ogs-full-20261117/"
    assert len(manifest["clips"]) == index["clips"] == 316
    assert len(manifest["playlists"]) == index["lessons"] == 248
    assert hashlib.sha256(manifest_bytes).hexdigest() == index["manifest_sha256"]
    playlist_hash = hashlib.sha256(
        json.dumps(manifest["playlists"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert playlist_hash == index["expected_playlist_sha256"]
    objects = index["objects"]
    assert len(objects) == 633 and objects[-1]["path"] == "manifest.json"
    backend = get_storage_backend()
    assert backend.is_remote and backend._bucket == "tutorial-assets"
    assert backend._public_base_url == "https://modelstella.com/media"
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        identity = dict(
            db.execute(
                text("SELECT current_database() AS database_name, system_identifier::text FROM pg_control_system()")
            )
            .mappings()
            .one()
        )
        db.rollback()
    assert (
        identity
        == index["prod_identity"]
        == {"database_name": "katrain_prod_20260725", "system_identifier": "7701028975512703016"}
    ), "PROD database identity differs"
    client, bucket = backend._client, backend._bucket
    assert "IfNoneMatch" in client.meta.service_model.operation_model("PutObject").input_shape.members
    by_id = {clip["id"]: clip for clip in manifest["clips"]}
    expected = {}
    for clip in by_id.values():
        assert set(clip["profiles"]) == {"kiosk-7-v1", "galaxy-4k-v1"}
        for profile, asset in clip["profiles"].items():
            path = f'clips/{clip["id"]}/{profile}.mp4'
            assert asset["url"] == "https://modelstella.com/media/" + index["prefix"] + path
            expected[path] = asset
    assert len(expected) == 632
    assert {obj["path"] for obj in objects} == set(expected) | {"manifest.json"}
    assert len({obj["key"] for obj in objects}) == 633
    assert set(manifest["playlists"]) and all(
        values and len(values) == len(set(values)) and all(v in by_id for v in values)
        for values in manifest["playlists"].values()
    )
    for obj in objects:
        assert obj["key"] == index["prefix"] + obj["path"]
        if obj["path"] != "manifest.json":
            asset = expected[obj["path"]]
            assert (asset["sha256"], asset["bytes"]) == (obj["sha256"], obj["bytes"])
            assert re.fullmatch(
                r"https://go\.sailorvoyage\.top/media/tutorial_assets/[a-z0-9-]+/media/[0-9a-f]{32}/video-2d-(?:kiosk-7-v1|galaxy-4k-v1)\.mp4",
                obj["source_url"],
            )
        else:
            assert len(manifest_bytes) == obj["bytes"] and obj["sha256"] == index["manifest_sha256"]

    def stored_matches(obj):
        try:
            response = client.get_object(Bucket=bucket, Key=obj["key"])
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in ("NoSuchKey", "404"):
                return False
            raise
        with response["Body"] as body:
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: body.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
        assert (
            size == obj["bytes"] and digest.hexdigest() == obj["sha256"]
        ), "Existing object differs; refusing overwrite"
        assert response["ContentType"] == obj["content_type"]
        return True

    # Full index validation is done before the first remote write.
    print(
        json.dumps(
            {
                "validated": True,
                "publish": args.publish,
                "workers": args.workers,
                "objects": len(objects),
                "identity": identity,
            }
        ),
        flush=True,
    )
    if not args.publish:
        return

    def publish(obj):
        if stored_matches(obj):
            return {"path": obj["path"], "state": "already-identical", "sha256_verified": True}
        data = manifest_bytes if obj["path"] == "manifest.json" else None
        if data is None and args.source_root:
            data = (args.source_root / obj["path"]).read_bytes()
            assert (
                len(data) == obj["bytes"] and hashlib.sha256(data).hexdigest() == obj["sha256"]
            ), "Cached TEST source fingerprint differs"
        if data is None:
            for attempt in range(2):
                try:
                    with urlopen(obj["source_url"], timeout=60) as source:
                        data = source.read(obj["bytes"] + 1)
                    assert (
                        len(data) == obj["bytes"] and hashlib.sha256(data).hexdigest() == obj["sha256"]
                    ), "TEST source fingerprint differs"
                    break
                except Exception:
                    if attempt:
                        raise
                    time.sleep(1)
        try:
            client.put_object(
                Bucket=bucket,
                Key=obj["key"],
                Body=data,
                ContentType=obj["content_type"],
                CacheControl="public,max-age=31536000,immutable",
                Metadata={"sha256": obj["sha256"], "release-id": index["release_id"]},
                IfNoneMatch="*",
            )
            state = "created"
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) not in ("PreconditionFailed", "412"):
                raise
            state = "already-identical"
        assert stored_matches(obj), "Uploaded object missing"
        return {"path": obj["path"], "state": state, "sha256_verified": True}

    receipt = {"release_id": index["release_id"], "identity": identity, "objects": []}
    pool = ThreadPoolExecutor(max_workers=args.workers)
    try:
        futures = [pool.submit(publish, obj) for obj in objects[:-1]]
        for number, future in enumerate(as_completed(futures), 1):
            result = future.result()
            receipt["objects"].append(result)
            if number % 40 == 0 or number == 632:
                print(json.dumps({"verified_media": number, "total_media": 632}), flush=True)
    except BaseException:
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    receipt["objects"].append(publish(objects[-1]))
    receipt.update(
        published_at=datetime.now(timezone.utc).isoformat(),
        manifest_url="https://modelstella.com/media/" + index["prefix"] + "manifest.json",
    )
    (args.bundle / "publication-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps({"published": True, "objects": len(receipt["objects"]), "manifest_url": receipt["manifest_url"]}),
        flush=True,
    )


if __name__ == "__main__":
    main()
