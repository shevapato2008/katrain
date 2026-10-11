"""Read-only PROD 597 progress delta for the exact 174 literal raw-event albums."""

from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import Column, String, create_engine, func, select, text
from sqlalchemy.orm import Session, column_property, defer

from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuNameBatch, KifuNameChange,
    KifuRawEventValue,
)
from katrain.web.kifu.identity import (
    PRIMARY_NAME_LANGUAGES, _approved_raw_event_names, live_event_selections,
    obscured_program_event_ids, strict_slot_approvals,
)
from katrain.web.kifu.name_candidates import canonical_sha256


if not __debug__:
    raise RuntimeError('bounded stats assertions must be enabled')
D = Path('/work')
LANGUAGES = sorted(PRIMARY_NAME_LANGUAGES)
BATCH_ID = 597

if not hasattr(KifuAlbum, 'list_hidden_reason'):
    KifuAlbum.__table__.append_column(Column('list_hidden_reason', String(64)))
    KifuAlbum.list_hidden_reason = column_property(KifuAlbum.__table__.c.list_hidden_reason)


def load():
    baseline = json.loads((D / '595-PROD-progress-actual.json').read_text())
    artifact = json.loads((D / 'PROD-name-approved.json').read_text())
    capture_path = D / 'PROD-postowner-capture.json.gz'
    capture = json.loads(gzip.decompress(capture_path.read_bytes()))
    request = json.loads((D / 'name-review-request-unsigned.json').read_text())
    apply = json.loads(gzip.decompress((D / 'PROD-name-apply.json.gz').read_bytes()))
    assert baseline['applied_batch_id'] == 595
    assert artifact['status'] == 'root_reviewed_name_bundle' and capture['ready_for_unsigned_name_review']
    assert hashlib.sha256(capture_path.read_bytes()).hexdigest() == request['postowner_capture_file_sha256']['PROD']
    assert artifact['postowner_capture_file_sha256'] == request['postowner_capture_file_sha256']['PROD']
    assert apply['batch_id'] == BATCH_ID and apply['status'] == 'applied'
    assert apply['bundle_canonical_sha256'] == canonical_sha256(artifact['name_bundle'])
    assert len(artifact['name_bundle']['owners']) == 150 and len(artifact['name_bundle']['candidates']) == 750
    ids = sorted({album_id for row in capture['records'] for album_id in row['album_ids']})
    raws = {row['raw_value'] for row in capture['records']}
    assert len(raws) == 150 and len(ids) == 174
    return baseline, artifact, capture, ids, raws


def bounded(db, ids, raws):
    count = Counter()
    for offset in range(0, len(ids), 200):
        page_ids = ids[offset:offset + 200]
        albums = (db.query(KifuAlbum)
                  .options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                  .filter(KifuAlbum.id.in_(page_ids)).order_by(KifuAlbum.id).all())
        assert [album.id for album in albums] == page_ids
        selected = live_event_selections(db, albums)
        obscured = obscured_program_event_ids(db, albums, selected_events=selected)
        assert not selected and not obscured.intersection(page_ids)
        counts = {album.id: [0, 0, 0] for album in albums}
        for language in LANGUAGES:
            approvals = strict_slot_approvals(db, albums, language,
                                              selected_events=selected, obscured_event_ids=obscured)
            for album in albums:
                black, white, event = approvals[album.id]
                assert event is not None
                counts[album.id][0] += black is not None
                counts[album.id][1] += white is not None
                counts[album.id][2] += event is not None
        for album in albums:
            assert album.event in raws and album.event_id is None
            assert album.duplicate_of_id is None and album.list_hidden_reason is None
            black, white, event = [value == len(LANGUAGES) for value in counts[album.id]]
            assert event
            count['games'] += 1
            count['event_before_none'] += 1
            count['event_after_qualified'] += 1
            count['both_players_before_and_after'] += black and white
            count['raw_cards_after'] += black and white and event
    assert count['games'] == count['event_before_none'] == count['event_after_qualified'] == 174
    assert count['raw_cards_after'] == count['both_players_before_and_after']
    return dict(count)


def raw_title_denominators(db):
    by_language = {}
    for language in LANGUAGES:
        by_language[language] = {
            name.raw_event_id for name, _raw, _scope in _approved_raw_event_names(db, lang=language)
            if name.decision_kind == 'translated'
            and name.generation_rule_version == 'raw-event-title-translation-v1'
        }
    complete = set.intersection(*(by_language[language] for language in LANGUAGES))
    distinct_album_raw = db.execute(select(func.count(func.distinct(KifuAlbum.event)))).scalar_one()
    raw_owner_total = db.execute(select(func.count(KifuRawEventValue.id))).scalar_one()
    return {'five_language_literal_raw_title_owners': len(complete),
            'distinct_album_raw_event_values': distinct_album_raw,
            'raw_event_owner_rows': raw_owner_total,
            'five_language_literal_raw_title_owner_ids_sha256': canonical_sha256(sorted(complete))}


def report(engine):
    baseline, artifact, capture, ids, raws = load()
    bundle_sha = canonical_sha256(artifact['name_bundle'])
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            conn.execute(text('SET TRANSACTION READ ONLY'))
            with Session(bind=conn) as db:
                batch = db.get(KifuNameBatch, BATCH_ID)
                assert batch is not None and batch.status == 'applied' and batch.bundle_sha256 == bundle_sha
                changes = db.execute(select(KifuNameChange.target_table, KifuNameChange.before_image).where(
                    KifuNameChange.batch_id == BATCH_ID)).all()
                ledger = Counter(target for target, _before in changes)
                assert ledger == {'kifu_raw_event_names': 750, 'kifu_name_research_evidence': 750}
                assert all(before is None for _target, before in changes)
                games, black, white, linked_events = db.execute(select(
                    func.count(KifuAlbum.id), func.count(KifuAlbum.black_player_id),
                    func.count(KifuAlbum.white_player_id), func.count(KifuAlbum.event_id)
                )).one()
                assert games == baseline['games']
                assert black + white == baseline['linked_player_slots']
                assert linked_events == baseline['linked_event_games']
                assert db.execute(select(func.count(KifuAlbumEventSelection.album_id)).where(
                    KifuAlbumEventSelection.album_id.in_(ids))).scalar_one() == 0
                delta = bounded(db, ids, raws)
                denominators = raw_title_denominators(db)
                assert denominators['five_language_literal_raw_title_owners'] >= 150
    current = dict(baseline)
    current['observed_at'] = datetime.now(timezone.utc).isoformat()
    current['baseline_batch_id'] = 595
    current['applied_batch_id'] = BATCH_ID
    current['raw_event_five_lang_games'] += delta['event_after_qualified']
    current['complete_five_lang_raw_games'] += delta['raw_cards_after']
    current['complete_five_lang_display_games'] = (current['complete_five_lang_games']
                                                   + current['complete_five_lang_raw_games'])
    current['coverage_method'] = (
        '批次597后 r6 native strict_slot_approvals；仅174局原始赛事受影响棋谱模拟批次前赛事槽为空，'
        '按实际双方棋手资格计算完整卡片增量；其余棋局继承实际595基线，未作全库严格卡片扫描')
    for key in ('raw_event_five_lang_games', 'complete_five_lang_raw_games',
                'complete_five_lang_display_games'):
        current[key + '_pct'] = round(100 * current[key] / current['games'], 4)
    current['raw_title_coverage'] = denominators
    audit = {'environment': 'PROD', 'batch_id': BATCH_ID, 'bundle_sha256': bundle_sha,
             'read_only': True, 'bounded_scope': delta,
             'ledger_targets': dict(ledger), 'raw_title_coverage': denominators,
             'baseline_batch_id': 595,
             'note': 'Other catalog and album coverage counts inherit the actual 595 baseline.'}
    return {'progress': current, 'audit': audit}


if __name__ == '__main__':
    engine = create_engine(os.environ['KATRAIN_DATABASE_URL'],
                           connect_args={'options': '-c default_transaction_read_only=on'})
    try:
        output = report(engine)
    finally:
        engine.dispose()
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
