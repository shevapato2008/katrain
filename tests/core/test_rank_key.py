import math

import pytest

from katrain.core.lang import rank_key


@pytest.mark.parametrize(
    ("rank", "expected"),
    [
        (None, ""),
        (math.nan, ""),
        (-5, "6k"),
        (0, "1k"),
        (1, "1d"),
        (3, "3d"),
    ],
)
def test_rank_key_uses_language_neutral_integer_boundaries(rank, expected):
    assert rank_key(rank) == expected
