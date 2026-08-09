from pathlib import Path


def test_web_image_installs_bundled_xiangqi_ranked_package():
    requirements = (Path(__file__).parents[2] / "requirements-web.txt").read_text()

    assert "-e packages/smartbox-xiangqi-ranked" in requirements.splitlines()
