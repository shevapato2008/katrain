"""Contract tests for S3StorageBackend, using moto to mock S3 in-memory.

Task 2 of superpowers/tracks/tutorial-database/plan.md. The same backend class
talks to MinIO (phase 1) and Aliyun OSS (phase 2); moto stands in for both.
"""
import boto3
import pytest
from moto import mock_aws

from katrain.web.core.storage.base import StorageBackend
from katrain.web.core.storage.s3 import S3StorageBackend

BUCKET = "tutorial-assets"
KEY = "tutorial_assets/book/video/fig_1.mp4"
DATA = bytes(range(256)) * 8  # 2048 bytes


@pytest.fixture
def s3_backend():
    with mock_aws():
        # Create the bucket moto will serve.
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        yield S3StorageBackend(
            bucket=BUCKET,
            endpoint_url=None,
            region="us-east-1",
            access_key="testing",
            secret_key="testing",
            public_base_url="https://media.example.com/tutorial-assets",
            use_presigned=False,
        )


class TestS3StorageBackend:
    def test_is_a_storage_backend(self, s3_backend):
        assert isinstance(s3_backend, StorageBackend)

    def test_is_remote(self, s3_backend):
        # S3 backend -> clients are 302-redirected to public_url.
        assert s3_backend.is_remote is True

    def test_put_then_exists(self, s3_backend):
        assert s3_backend.exists(KEY) is False
        s3_backend.put(KEY, DATA, content_type="video/mp4")
        assert s3_backend.exists(KEY) is True

    def test_put_accepts_fileobj(self, s3_backend):
        import io

        s3_backend.put(KEY, io.BytesIO(DATA))
        assert s3_backend.read(KEY) == DATA

    def test_size(self, s3_backend):
        s3_backend.put(KEY, DATA)
        assert s3_backend.size(KEY) == len(DATA)

    def test_read_full(self, s3_backend):
        s3_backend.put(KEY, DATA)
        assert s3_backend.read(KEY) == DATA

    def test_read_range(self, s3_backend):
        s3_backend.put(KEY, DATA)
        assert s3_backend.read_range(KEY, 10, 20) == DATA[10:30]

    def test_size_missing_raises(self, s3_backend):
        with pytest.raises(FileNotFoundError):
            s3_backend.size("tutorial_assets/nope.mp4")

    def test_content_type_and_cache_control_set(self, s3_backend):
        s3_backend.put(KEY, DATA, content_type="video/mp4")
        head = s3_backend._client.head_object(Bucket=BUCKET, Key=KEY)
        assert head["ContentType"] == "video/mp4"
        assert "max-age" in head["CacheControl"]

    def test_content_type_inferred_from_key(self, s3_backend):
        s3_backend.put("tutorial_assets/book/audio/fig_1.mp3", DATA)
        head = s3_backend._client.head_object(Bucket=BUCKET, Key="tutorial_assets/book/audio/fig_1.mp3")
        assert head["ContentType"] == "audio/mpeg"

    def test_public_url_uses_base_url(self, s3_backend):
        assert s3_backend.public_url(KEY) == f"https://media.example.com/tutorial-assets/{KEY}"

    def test_public_url_normalizes_key(self, s3_backend):
        assert s3_backend.public_url("data/" + KEY) == f"https://media.example.com/tutorial-assets/{KEY}"

    def test_key_normalized_on_put(self, s3_backend):
        s3_backend.put("/" + KEY, DATA)
        assert s3_backend.exists(KEY) is True

    def test_traversal_rejected(self, s3_backend):
        with pytest.raises(ValueError):
            s3_backend.put("../escape.mp4", DATA)

    def test_list_keys_under_prefix(self, s3_backend):
        # Single list_objects call replaces N per-section head_object probes.
        s3_backend.put("tutorial_assets/book/video/section_1.mp4", DATA)
        s3_backend.put("tutorial_assets/book/video/section_2.mp4", DATA)
        s3_backend.put("tutorial_assets/book/audio/fig_1.mp3", DATA)
        assert s3_backend.list_keys("tutorial_assets/book/video/") == {
            "tutorial_assets/book/video/section_1.mp4",
            "tutorial_assets/book/video/section_2.mp4",
        }

    def test_list_keys_missing_prefix_is_empty(self, s3_backend):
        assert s3_backend.list_keys("tutorial_assets/nope/video/") == set()


class TestS3PresignedUrls:
    @pytest.fixture
    def presigned_backend(self):
        with mock_aws():
            boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
            yield S3StorageBackend(
                bucket=BUCKET,
                endpoint_url=None,
                region="us-east-1",
                access_key="testing",
                secret_key="testing",
                public_base_url="",
                use_presigned=True,
                presign_ttl_sec=900,
            )

    def test_public_url_is_signed(self, presigned_backend):
        presigned_backend.put(KEY, DATA)
        url = presigned_backend.public_url(KEY)
        assert KEY in url
        assert "X-Amz-Signature" in url or "Signature" in url
