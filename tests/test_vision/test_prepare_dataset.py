from pathlib import Path

from katrain.vision.tools.prepare_dataset import merge_datasets, split_dataset, validate_dataset, write_data_yaml


def _make_image_label_dirs(tmp_path, n_images=10):
    """Helper to create fake image + label directories."""
    img_dir = tmp_path / "images"
    lbl_dir = tmp_path / "labels"
    img_dir.mkdir()
    lbl_dir.mkdir()
    for i in range(n_images):
        (img_dir / f"img_{i:03d}.jpg").write_bytes(b"fake")
        (lbl_dir / f"img_{i:03d}.txt").write_text(f"0 0.5 0.5 0.05 0.05\n")
    return img_dir, lbl_dir


class TestSplitDataset:
    def test_basic_split(self, tmp_path):
        img_dir, lbl_dir = _make_image_label_dirs(tmp_path, 10)
        output = tmp_path / "output"

        stats = split_dataset(img_dir, lbl_dir, output, train_ratio=0.8, seed=42)

        assert stats["train"] == 8
        assert stats["val"] == 2
        assert stats["missing_labels"] == 0

        train_imgs = list((output / "images" / "train").iterdir())
        val_imgs = list((output / "images" / "val").iterdir())
        assert len(train_imgs) == 8
        assert len(val_imgs) == 2

        train_lbls = list((output / "labels" / "train").iterdir())
        val_lbls = list((output / "labels" / "val").iterdir())
        assert len(train_lbls) == 8
        assert len(val_lbls) == 2

    def test_reproducible_with_seed(self, tmp_path):
        img_dir, lbl_dir = _make_image_label_dirs(tmp_path, 20)
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"

        split_dataset(img_dir, lbl_dir, out1, seed=123)
        split_dataset(img_dir, lbl_dir, out2, seed=123)

        files1 = sorted(f.name for f in (out1 / "images" / "train").iterdir())
        files2 = sorted(f.name for f in (out2 / "images" / "train").iterdir())
        assert files1 == files2

    def test_missing_labels(self, tmp_path):
        img_dir = tmp_path / "images"
        lbl_dir = tmp_path / "labels"
        img_dir.mkdir()
        lbl_dir.mkdir()
        (img_dir / "img_000.jpg").write_bytes(b"fake")
        # No label file
        output = tmp_path / "output"
        stats = split_dataset(img_dir, lbl_dir, output)
        assert stats["missing_labels"] == 1


class TestMergeDatasets:
    def test_merge_no_collision(self, tmp_path):
        base = tmp_path / "base"
        extra = tmp_path / "extra"
        output = tmp_path / "output"

        for ds, prefix in [(base, "base"), (extra, "extra")]:
            for split in ("train", "val"):
                (ds / "images" / split).mkdir(parents=True)
                (ds / "labels" / split).mkdir(parents=True)
                (ds / "images" / split / f"{prefix}_1.jpg").write_bytes(b"fake")
                (ds / "labels" / split / f"{prefix}_1.txt").write_text("0 0.5 0.5 0.05 0.05\n")

        stats = merge_datasets(base, extra, output)
        assert stats["base"] == 2
        assert stats["merged"] == 2
        assert (output / "data.yaml").exists()

    def test_merge_with_collision(self, tmp_path):
        base = tmp_path / "base"
        extra = tmp_path / "extra"
        output = tmp_path / "output"

        for ds in (base, extra):
            (ds / "images" / "train").mkdir(parents=True)
            (ds / "labels" / "train").mkdir(parents=True)
            (ds / "images" / "train" / "same.jpg").write_bytes(b"fake")
            (ds / "labels" / "train" / "same.txt").write_text("0 0.5 0.5 0.05 0.05\n")

        merge_datasets(base, extra, output)

        files = sorted(f.name for f in (output / "images" / "train").iterdir())
        assert len(files) == 2
        assert "same.jpg" in files
        assert "merge_same.jpg" in files


class TestValidateDataset:
    def test_valid_dataset(self, tmp_path):
        for split in ("train", "val"):
            (tmp_path / "images" / split).mkdir(parents=True)
            (tmp_path / "labels" / split).mkdir(parents=True)
            (tmp_path / "images" / split / "img.jpg").write_bytes(b"fake")
            (tmp_path / "labels" / split / "img.txt").write_text("0 0.5 0.5 0.05 0.05\n")
        write_data_yaml(tmp_path)

        result = validate_dataset(tmp_path)
        assert result["valid"]
        assert result["train_images"] == 1
        assert result["val_images"] == 1
        assert len(result["issues"]) == 0

    def test_missing_data_yaml(self, tmp_path):
        for split in ("train", "val"):
            (tmp_path / "images" / split).mkdir(parents=True)
            (tmp_path / "labels" / split).mkdir(parents=True)
        result = validate_dataset(tmp_path)
        assert not result["valid"]
        assert any("data.yaml" in i for i in result["issues"])

    def test_orphan_images(self, tmp_path):
        (tmp_path / "images" / "train").mkdir(parents=True)
        (tmp_path / "labels" / "train").mkdir(parents=True)
        (tmp_path / "images" / "val").mkdir(parents=True)
        (tmp_path / "labels" / "val").mkdir(parents=True)
        (tmp_path / "images" / "train" / "img.jpg").write_bytes(b"fake")
        # No matching label
        write_data_yaml(tmp_path)

        result = validate_dataset(tmp_path)
        assert any("without labels" in i for i in result["issues"])


class TestWriteDataYaml:
    def test_writes_yaml(self, tmp_path):
        write_data_yaml(tmp_path)
        content = (tmp_path / "data.yaml").read_text()
        assert "nc: 2" in content
        assert "black" in content
        assert "white" in content
        assert "images/train" in content
        assert "images/val" in content
