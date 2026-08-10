import subprocess
import sys
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSER = REPO_ROOT / "superpowers/tracks/galaxy-ui-redesign/compose_live_template_visuals.py"


def run_composer(visual_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMPOSER), "--visual-root", str(visual_root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_composes_same_size_sources_without_resizing(tmp_path):
    viewport = tmp_path / "2x2"
    viewport.mkdir()
    reference_pixels = [(10, 20, 30), (50, 60, 70), (90, 100, 110), (130, 140, 150)]
    implementation_pixels = [(10, 20, 30), (70, 60, 50), (90, 100, 110), (150, 120, 90)]
    reference = Image.new("RGB", (2, 2))
    reference.putdata(reference_pixels)
    implementation = Image.new("RGB", (2, 2))
    implementation.putdata(implementation_pixels)
    reference.save(viewport / "reference.png")
    implementation.save(viewport / "implementation.png")

    result = run_composer(tmp_path)

    assert result.returncode == 0, result.stderr
    with Image.open(viewport / "side-by-side.png") as side_by_side:
        assert side_by_side.size == (4, 2)
        assert list(side_by_side.crop((0, 0, 2, 2)).convert("RGB").getdata()) == reference_pixels
        assert list(side_by_side.crop((2, 0, 4, 2)).convert("RGB").getdata()) == implementation_pixels
    with Image.open(viewport / "overlay.png") as overlay:
        assert overlay.size == (2, 2)
        assert list(overlay.convert("RGB").getdata()) == list(
            Image.blend(reference, implementation, 0.5).getdata()
        )
    with Image.open(viewport / "diff.png") as difference:
        assert difference.size == (2, 2)
        difference_pixels = list(difference.convert("RGB").getdata())
        assert difference_pixels[0] == (0, 0, 0)
        assert difference_pixels[2] == (0, 0, 0)
        assert difference_pixels[1] != (0, 0, 0)
        assert difference_pixels[3] != (0, 0, 0)
    assert Image.open(viewport / "reference.png").size == (2, 2)
    assert Image.open(viewport / "implementation.png").size == (2, 2)


def test_rejects_mismatched_dimensions_and_names_viewport(tmp_path):
    viewport = tmp_path / "3x2"
    viewport.mkdir()
    Image.new("RGB", (3, 2)).save(viewport / "reference.png")
    Image.new("RGB", (2, 2)).save(viewport / "implementation.png")

    result = run_composer(tmp_path)

    assert result.returncode != 0
    assert "3x2" in result.stderr
    assert "dimensions" in result.stderr.lower()


def test_rejects_missing_source_and_names_viewport(tmp_path):
    viewport = tmp_path / "4x3"
    viewport.mkdir()
    Image.new("RGB", (4, 3)).save(viewport / "reference.png")

    result = run_composer(tmp_path)

    assert result.returncode != 0
    assert "4x3" in result.stderr
    assert "implementation.png" in result.stderr
