"""With parallax off, BoardStateExtractor must reproduce the pre-parallax outputs bit-for-bit
(prd P1-1 acceptance 1). The golden file names the commit it was generated on; see
board_state_corpus.py for what the corpus covers and how to regenerate it."""

import json

import pytest

from katrain.vision.board_state import BoardStateExtractor
from katrain.vision.parallax import ParallaxParams
from tests.test_vision.board_state_corpus import GOLDEN_PATH, run_all


def _golden():
    return json.loads(GOLDEN_PATH.read_text())


def _first_difference(got, want):
    for name in want:
        for i, (g, w) in enumerate(zip(got[name], want[name])):
            for key in w:
                if g[key] != w[key]:
                    return f"config={name} frame={i} key={key}"
    return None


def test_golden_records_its_source_commit():
    assert len(_golden()["generated_at_commit"]) == 40


@pytest.mark.parametrize(
    "make_extractor",
    [
        pytest.param(BoardStateExtractor, id="default"),
        pytest.param(lambda cfg: BoardStateExtractor(cfg, parallax=None), id="parallax-none"),
        pytest.param(lambda cfg: BoardStateExtractor(cfg, parallax=ParallaxParams(9.0, 19.6, 1.0)), id="parallax-k1"),
    ],
)
def test_extractor_reproduces_golden(make_extractor):
    want = _golden()["outputs"]
    got = json.loads(json.dumps(run_all(make_extractor)))
    assert _first_difference(got, want) is None, _first_difference(got, want)
    assert got == want
