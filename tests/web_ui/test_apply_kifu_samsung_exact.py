import json
from pathlib import Path

import pytest

from scripts.apply_kifu_samsung_exact import digest, execute


def test_exact_approved_scope_and_six_type_only():
    root = Path(__file__).resolve().parents[2]
    source = json.loads((root / 'docs/resource/kifu-event-samsung-read-only-review-2026-10-04.json').read_text())
    assert digest(source['albums']) == '81ec9f4131ca0e2d516348782e143ba1c1012fe6a5312379765349e4aef78a3f'
    assert [x[0] for x in source['albums'] if x[8] is None] == [28773,84471,92080,97284,119166,138885]


def test_scope_drift_rejected_before_database_access():
    with pytest.raises(ValueError, match='approval scope digest mismatch'):
        execute({'mode':'dry', 'scope':{'albums':[]}})


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match='unsupported mode'):
        execute({'mode':'unexpected', 'scope':{}})
