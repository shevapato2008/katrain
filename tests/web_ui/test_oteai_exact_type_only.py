import copy
import pytest
from scripts.apply_kifu_oteai_exact_type_only import freeze_plan, digest


def scope():
    allowed = [{'raw_event': 'Oteai Spring Session', 'album_count': 1, 'album_ids': [1]}]
    return {'exact_raw_allowlist': allowed, 'allowlist_sha256': digest(allowed),
            'album_preimages': [[1, 'Oteai Spring Session', None, None, None]],
            'held_raws': [{'raw_event': 'Probably Oteai', 'album_ids': [2]}]}


def test_frozen_scope_preserves_date_and_no_edition():
    s = scope()
    p = freeze_plan(s, s['album_preimages'], [[2, 'Probably Oteai', None, None, None]], 22, 'prod')
    assert p['rows'] == s['album_preimages']
    assert p['target_event_id'] == 22
    assert p['held_rows'][0][0] == 2


def test_extra_ids_and_preimage_drift_rejected():
    s = scope()
    with pytest.raises(ValueError, match='unapproved album IDs'):
        freeze_plan(s, s['album_preimages'] + [[3, 'Oteai Spring Session', None, None, None]], [], 1, 'test')
    rows = copy.deepcopy(s['album_preimages'])
    rows[0][2] = '2000'
    with pytest.raises(ValueError, match='approved preimage'):
        freeze_plan(s, rows, [], 22, 'prod')
    rows = copy.deepcopy(s['album_preimages'])
    rows[0][3] = 99
    with pytest.raises(ValueError, match='approved preimage'):
        freeze_plan(s, rows, [], 1, 'test')
