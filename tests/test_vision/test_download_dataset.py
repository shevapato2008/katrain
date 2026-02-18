from pathlib import Path

from katrain.vision.tools.download_dataset import convert_labels, remap_label_line


class TestRemapLabelLine:
    def test_keep_black(self):
        assert remap_label_line("0 0.5 0.5 0.05 0.05") == "0 0.5 0.5 0.05 0.05"

    def test_keep_white(self):
        assert remap_label_line("1 0.3 0.4 0.05 0.05") == "1 0.3 0.4 0.05 0.05"

    def test_drop_grid(self):
        assert remap_label_line("2 0.5 0.5 0.1 0.1") is None

    def test_unknown_class(self):
        assert remap_label_line("5 0.5 0.5 0.05 0.05") is None

    def test_empty_line(self):
        assert remap_label_line("") is None
        assert remap_label_line("  ") is None

    def test_custom_mapping(self):
        mapping = {0: 1, 1: 0}
        assert remap_label_line("0 0.5 0.5 0.05 0.05", mapping) == "1 0.5 0.5 0.05 0.05"
        assert remap_label_line("1 0.5 0.5 0.05 0.05", mapping) == "0 0.5 0.5 0.05 0.05"

    def test_preserves_coordinates(self):
        result = remap_label_line("0 0.123456 0.654321 0.051234 0.048765")
        assert result == "0 0.123456 0.654321 0.051234 0.048765"


class TestConvertLabels:
    def test_flat_structure(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "img1.jpg").write_bytes(b"fake_image")
        (source / "img1.txt").write_text("0 0.5 0.5 0.05 0.05\n2 0.3 0.3 0.1 0.1\n1 0.7 0.7 0.05 0.05\n")

        output = tmp_path / "output"
        stats = convert_labels(source, output)

        assert stats["images"] == 1
        assert stats["lines_kept"] == 2
        assert stats["lines_dropped"] == 1

    def test_roboflow_split_structure(self, tmp_path):
        source = tmp_path / "source"
        for split in ("train", "valid"):
            (source / split / "images").mkdir(parents=True)
            (source / split / "labels").mkdir(parents=True)
            (source / split / "images" / "img1.jpg").write_bytes(b"fake_image")
            (source / split / "labels" / "img1.txt").write_text("0 0.5 0.5 0.05 0.05\n2 0.3 0.3 0.1 0.1\n")

        output = tmp_path / "output"
        stats = convert_labels(source, output)

        assert stats["images"] == 2
        assert stats["lines_kept"] == 2
        assert stats["lines_dropped"] == 2

        # Check "valid" was renamed to "val"
        assert (output / "images" / "val").exists()
        assert (output / "labels" / "val").exists()
        assert not (output / "images" / "valid").exists()

    def test_data_yaml_created(self, tmp_path):
        source = tmp_path / "source"
        (source / "train" / "images").mkdir(parents=True)
        (source / "train" / "labels").mkdir(parents=True)
        (source / "train" / "images" / "img.jpg").write_bytes(b"fake")
        (source / "train" / "labels" / "img.txt").write_text("0 0.5 0.5 0.05 0.05\n")

        output = tmp_path / "output"
        convert_labels(source, output)

        yaml_path = output / "data.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "nc: 2" in content
        assert "black" in content
        assert "white" in content
