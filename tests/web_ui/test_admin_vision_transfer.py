"""Transfer real frozen bytes through an in-memory remote boundary, never SSH."""

import hashlib
from pathlib import Path
from threading import Event

import pytest

from test_admin_vision_dataset import builder, populate, session


@pytest.fixture
def frozen(session):
    populate(session)
    datasets = builder(session)
    version = datasets.freeze(session[1]["game_id"])
    return datasets, version


class MemoryRemote:
    """The adapter reports hashes of actual bytes, not copied expected digests."""

    def __init__(self):
        self.stage = {}
        self.final = None
        self.available = 10 * 1024**3
        self.writes = []
        self.publications = 0
        self.fail_write = None
        self.lose_receipt = False
        self.bad_receipt = False
        self.cancel = None

    def receipt(self, plan, files):
        from katrain.web.admin.vision_transfer import FileReceipt, TransferReceipt

        entries = tuple(
            FileReceipt(name, len(data), hashlib.sha256(data).hexdigest()) for name, data in sorted(files.items())
        )
        return TransferReceipt(plan.dataset_id, plan.manifest_sha256, entries)

    def inspect(self, config, plan):
        from katrain.web.admin.vision_transfer import RemoteSnapshot

        return RemoteSnapshot(
            self.available, self.receipt(plan, self.stage), self.receipt(plan, self.final) if self.final else None
        )

    def write_file(self, config, plan, entry, source, cancel_event):
        if self.fail_write == entry.name:
            raise OSError("interrupted")
        data = source.read_bytes()
        self.stage[entry.name] = data
        self.writes.append(entry.name)
        self.available -= len(data)
        if self.cancel:
            self.cancel.set()

    def publish(self, config, plan):
        self.final = dict(self.stage)
        self.stage = {}
        self.publications += 1
        if self.lose_receipt:
            self.lose_receipt = False
            raise OSError("response lost after atomic publish")
        if self.bad_receipt:
            self.final["unexpected.txt"] = b"not in frozen version"
        return self.receipt(plan, self.final)


def service(frozen, remote=None, **options):
    from katrain.web.admin.vision_transfer import TransferConfig, VisionDatasetTransfer

    config = TransferConfig(enabled=True, remote_root="/approved/vision-datasets", **options)
    return VisionDatasetTransfer(frozen[0], config=config, transport=remote or MemoryRemote())


def test_prepare_uses_frozen_assets_and_original_manifest_bytes(frozen):
    plan = service(frozen).prepare(frozen[1]["id"])
    directory = Path(frozen[1]["path"])
    assert plan.dataset_id == frozen[1]["id"]
    assert plan.manifest_sha256 == frozen[1]["manifest_sha256"]
    assert {entry.name for entry in plan.files} == set(frozen[1]["assets"]) | {"manifest.json"}
    assert plan.total_bytes == sum((directory / entry.name).stat().st_size for entry in plan.files)
    assert {entry.name: entry.sha256 for entry in plan.files}["manifest.json"] == hashlib.sha256(
        (directory / "manifest.json").read_bytes()
    ).hexdigest()


def test_default_or_unverified_configuration_never_calls_transport(frozen):
    from katrain.web.admin.vision_transfer import TransferConfig, VisionDatasetTransfer, VisionTransferError

    class NeverRemote:
        def inspect(self, *args):
            pytest.fail("disabled configuration reached remote boundary")

    for config in (TransferConfig(), TransferConfig(enabled=True), TransferConfig(host="elsewhere")):
        with pytest.raises(VisionTransferError):
            VisionDatasetTransfer(frozen[0], config=config, transport=NeverRemote()).transfer(
                frozen[1]["id"], confirmed=True
            )
    with pytest.raises(VisionTransferError):
        service(frozen, NeverRemote()).transfer(frozen[1]["id"], confirmed=False)


def test_upload_verifies_every_file_and_repeated_final_is_idempotent(frozen):
    remote = MemoryRemote()
    upload = service(frozen, remote)
    result = upload.transfer(frozen[1]["id"], confirmed=True)
    assert result.state == "uploaded" and result.idempotent is False
    assert remote.final == {
        entry.name: (Path(frozen[1]["path"]) / entry.name).read_bytes() for entry in result.plan.files
    }
    repeated = upload.transfer(frozen[1]["id"], confirmed=True)
    assert repeated.state == "uploaded" and repeated.idempotent is True
    assert remote.publications == 1 and len(remote.writes) == len(result.plan.files)


def test_insufficient_capacity_does_not_write_or_publish(frozen):
    from katrain.web.admin.vision_transfer import VisionTransferError

    remote = MemoryRemote()
    remote.available = 1
    with pytest.raises(VisionTransferError) as error:
        service(frozen, remote).transfer(frozen[1]["id"], confirmed=True)
    assert error.value.status_code == 507
    assert not remote.writes and remote.publications == 0


def test_interrupted_upload_resumes_only_matching_completed_files(frozen):
    remote = MemoryRemote()
    upload = service(frozen, remote)
    plan = upload.prepare(frozen[1]["id"])
    remote.fail_write = plan.files[1].name
    assert upload.transfer(plan.dataset_id, confirmed=True).state == "interrupted"
    assert remote.publications == 0 and remote.writes == [plan.files[0].name]
    remote.fail_write = None
    assert upload.transfer(plan.dataset_id, confirmed=True).state == "uploaded"
    assert remote.writes.count(plan.files[0].name) == 1


def test_cancel_preserves_stage_without_publishing(frozen):
    remote, event = MemoryRemote(), Event()
    remote.cancel = event
    result = service(frozen, remote).transfer(frozen[1]["id"], confirmed=True, cancel_event=event)
    assert result.state == "cancelled" and remote.stage and remote.final is None
    assert remote.publications == 0


def test_resume_replaces_staged_file_with_wrong_actual_hash(frozen):
    remote = MemoryRemote()
    upload = service(frozen, remote)
    plan = upload.prepare(frozen[1]["id"])
    remote.stage[plan.files[0].name] = b"partial or changed"
    result = upload.transfer(plan.dataset_id, confirmed=True)
    assert result.state == "uploaded"
    assert plan.files[0].name in remote.writes


def test_write_ack_without_matching_remote_bytes_never_publishes(frozen):
    from katrain.web.admin.vision_transfer import VisionTransferError

    class DamagedWrite(MemoryRemote):
        def write_file(self, config, plan, entry, source, cancel_event):
            super().write_file(config, plan, entry, source, cancel_event)
            self.stage[entry.name] = b"truncated"

    remote = DamagedWrite()
    with pytest.raises(VisionTransferError):
        service(frozen, remote).transfer(frozen[1]["id"], confirmed=True)
    assert remote.publications == 0 and remote.final is None


def test_cancelled_before_start_does_not_probe_remote(frozen):
    class NeverRemote:
        def inspect(self, *args):
            pytest.fail("pre-cancelled transfer probed remote")

    event = Event()
    event.set()
    assert (
        service(frozen, NeverRemote()).transfer(frozen[1]["id"], confirmed=True, cancel_event=event).state
        == "cancelled"
    )


def test_receipt_loss_is_unverified_then_recovered_without_overwriting(frozen):
    remote = MemoryRemote()
    remote.lose_receipt = True
    upload = service(frozen, remote)
    assert upload.transfer(frozen[1]["id"], confirmed=True).state == "unverified"
    assert remote.final and remote.publications == 1
    recovered = upload.transfer(frozen[1]["id"], confirmed=True)
    assert recovered.state == "uploaded" and recovered.idempotent is True
    assert remote.publications == 1


def test_mismatched_final_receipt_never_reports_uploaded(frozen):
    from katrain.web.admin.vision_transfer import VisionTransferError

    remote = MemoryRemote()
    remote.bad_receipt = True
    upload = service(frozen, remote)
    assert upload.transfer(frozen[1]["id"], confirmed=True).state == "unverified"
    with pytest.raises(VisionTransferError) as error:
        upload.transfer(frozen[1]["id"], confirmed=True)
    assert error.value.status_code == 409 and remote.publications == 1


@pytest.mark.parametrize("dataset_id", ["../outside", "dataset-bad", "/tmp/version"])
def test_only_controlled_dataset_ids_are_accepted(frozen, dataset_id):
    from katrain.web.admin.vision_transfer import VisionTransferError

    with pytest.raises(VisionTransferError):
        service(frozen).prepare(dataset_id)


def test_corrupt_source_and_size_limit_refuse_before_remote_write(frozen):
    from katrain.web.admin.vision_transfer import VisionDatasetTransfer, VisionTransferError

    with pytest.raises(VisionTransferError):
        VisionDatasetTransfer(frozen[0], max_bytes=1).prepare(frozen[1]["id"])
    image = Path(frozen[1]["path"]) / frozen[1]["samples"][0]["image"]
    image.chmod(0o644)
    image.write_bytes(b"changed")
    with pytest.raises(VisionTransferError):
        service(frozen).prepare(frozen[1]["id"])
