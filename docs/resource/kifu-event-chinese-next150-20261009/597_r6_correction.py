"""Read-only r5→r6 mixed-game qualification correction for PROD batch 597.

Scan strict slots only for the 174 batch albums and albums of older literal
owners that r6 qualifies in five languages but exact r5 rejects in all five.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, defer

from katrain.web.core.models_db import (
    KifuAlbum, KifuNameBatch, KifuNameChange, KifuNameResearchEvidence, KifuRawEventValue,
)
from katrain.web.kifu.identity import (
    _approved_raw_event_names, live_event_selections, obscured_program_event_ids,
    strict_slot_approvals,
)
from katrain.web.kifu.name_candidates import canonical_sha256

from backport_mixed_game import NATIVE_SHA256, REPLACEMENTS


D = Path('/work')
NATIVE = Path('/app/katrain/web/kifu/raw_event_translation.py')
R6_SHA256 = '0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f'
LANGS = ('cn', 'en', 'jp', 'ko', 'tw')
EXPECTED_OLDER_RESTORED = 1241
if not __debug__:
    raise RuntimeError('stats assertions must be enabled')


def load_bounded_stats():
    spec = importlib.util.spec_from_file_location('batch597_bounded_stats', D / '597_bounded_stats.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_r5_eligibility():
    r6_bytes = NATIVE.read_bytes()
    assert hashlib.sha256(r6_bytes).hexdigest() == R6_SHA256
    source = r6_bytes.decode('utf-8')
    for old, new in reversed(REPLACEMENTS):
        assert source.count(new) == 1
        source = source.replace(new, old, 1)
    r5_bytes = source.encode('utf-8')
    assert hashlib.sha256(r5_bytes).hexdigest() == NATIVE_SHA256
    module = ModuleType('exact_r5_raw_event_translation')
    exec(compile(source, str(NATIVE) + ':reversed-to-r5', 'exec'), module.__dict__)
    return module.eligible_literal_raw_name


def chunks(values, size=500):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def complete_qualified_names(db):
    by_lang = {}
    for lang in LANGS:
        rows = {}
        for name, _raw, _scope in _approved_raw_event_names(db, lang=lang):
            if (name.decision_kind != 'translated'
                    or name.generation_rule_version != 'raw-event-title-translation-v1'):
                continue
            assert name.raw_event_id not in rows
            rows[name.raw_event_id] = name
        by_lang[lang] = rows
    complete = set.intersection(*(set(by_lang[lang]) for lang in LANGS))
    return by_lang, complete


def classify_old_owners(db, by_lang, complete, current_owner_ids, baseline, r5_eligible):
    older = complete - current_owner_ids
    owners = {}
    for ids in chunks(sorted(older)):
        owners.update({row.id: row for row in db.scalars(
            select(KifuRawEventValue).where(KifuRawEventValue.id.in_(ids)))})
    assert set(owners) == older
    evidence_ids = {by_lang[lang][owner_id].evidence_id for owner_id in older for lang in LANGS}
    evidences = {}
    for ids in chunks(sorted(evidence_ids)):
        evidences.update({row.id: row for row in db.scalars(
            select(KifuNameResearchEvidence).where(KifuNameResearchEvidence.id.in_(ids)))})
    assert set(evidences) == evidence_ids
    stable, restored = set(), set()
    for owner_id in sorted(older):
        owner = owners[owner_id]
        accepted = [r5_eligible(vars(by_lang[lang][owner_id]),
                                vars(evidences[by_lang[lang][owner_id].evidence_id]),
                                vars(owner)) for lang in LANGS]
        if all(accepted):
            stable.add(owner_id)
        else:
            assert not any(accepted), (owner_id, accepted)
            review = owner.review_metadata or {}
            parts = (owner.parsed_data or {}).get('structure', {}).get('parts', [])
            assert review.get('sgf_literal', {}).get('profile') == 'sgf_chinese_mixed'
            assert any(part.get('kind') == 'game' for part in parts)
            restored.add(owner_id)
    assert len(stable) == baseline['raw_title_coverage']['five_language_literal_raw_title_owners']
    assert canonical_sha256(sorted(stable)) == baseline['raw_title_coverage'][
        'five_language_literal_raw_title_owner_ids_sha256']
    assert len(restored) == EXPECTED_OLDER_RESTORED
    assert len(complete) == len(stable) + len(current_owner_ids) + len(restored)
    return owners, stable, restored


def restored_album_delta(db, restored_raws):
    count = Counter()
    album_ids = []
    for raws in chunks(sorted(restored_raws)):
        album_ids.extend(db.scalars(select(KifuAlbum.id).where(
            KifuAlbum.event.in_(raws), KifuAlbum.event_id.is_(None),
            KifuAlbum.duplicate_of_id.is_(None), KifuAlbum.list_hidden_reason.is_(None))))
    album_ids = sorted(album_ids)
    assert len(album_ids) == len(set(album_ids))
    qualified_ids = []
    for ids in chunks(album_ids, 200):
        albums = (db.query(KifuAlbum).options(defer(KifuAlbum.sgf_content), defer(KifuAlbum.search_text))
                  .filter(KifuAlbum.id.in_(ids)).order_by(KifuAlbum.id).all())
        assert [album.id for album in albums] == ids
        selected = live_event_selections(db, albums)
        obscured = obscured_program_event_ids(db, albums, selected_events=selected)
        count['excluded_selection_or_obscured'] += sum(
            album.id in selected or album.id in obscured for album in albums)
        eligible = [album for album in albums if album.id not in selected and album.id not in obscured]
        if not eligible:
            continue
        approvals = {lang: strict_slot_approvals(db, eligible, lang,
                     selected_events={}, obscured_event_ids=set()) for lang in LANGS}
        for album in eligible:
            assert album.event in restored_raws and album.event_id is None
            assert album.duplicate_of_id is None and album.list_hidden_reason is None
            assert all(approvals[lang][album.id][2] is not None for lang in LANGS), album.id
            black = all(approvals[lang][album.id][0] is not None for lang in LANGS)
            white = all(approvals[lang][album.id][1] is not None for lang in LANGS)
            count['event_after_qualified'] += 1
            count['raw_cards_after'] += black and white
            qualified_ids.append(album.id)
    count['candidate_public_null_albums'] = len(album_ids)
    count['eligible_public_null_albums'] = len(qualified_ids)
    count['event_after_qualified'] += 0
    count['raw_cards_after'] += 0
    count['excluded_selection_or_obscured'] += 0
    assert count['candidate_public_null_albums'] == (
        count['eligible_public_null_albums'] + count['excluded_selection_or_obscured'])
    assert count['event_after_qualified'] == count['eligible_public_null_albums']
    return dict(count), canonical_sha256(qualified_ids)


def report(engine):
    stats = load_bounded_stats()
    baseline, artifact, capture, new_ids, new_raws = stats.load()
    current_owner_ids = {row['owner']['id'] for row in capture['records']}
    assert len(current_owner_ids) == len(new_raws) == 150
    r5_eligible = exact_r5_eligibility()
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            conn.execute(text('SET TRANSACTION READ ONLY'))
            with Session(bind=conn) as db:
                batch = db.get(KifuNameBatch, 597)
                bundle_sha = canonical_sha256(artifact['name_bundle'])
                assert batch is not None and batch.status == 'applied' and batch.bundle_sha256 == bundle_sha
                changes = db.execute(select(KifuNameChange.target_table, KifuNameChange.before_image).where(
                    KifuNameChange.batch_id == 597)).all()
                assert Counter(target for target, _ in changes) == {
                    'kifu_raw_event_names': 750, 'kifu_name_research_evidence': 750}
                assert all(before is None for _, before in changes)
                games, player_links, event_links, hidden = db.execute(select(
                    func.count(KifuAlbum.id),
                    func.count(KifuAlbum.black_player_id) + func.count(KifuAlbum.white_player_id),
                    func.count(KifuAlbum.event_id),
                    func.count(KifuAlbum.list_hidden_reason),
                )).one()
                assert (games, player_links, event_links, hidden) == (
                    baseline['games'], baseline['linked_player_slots'],
                    baseline['linked_event_games'], baseline['hidden_games'])
                new_delta = stats.bounded(db, new_ids, new_raws)
                assert new_delta['event_after_qualified'] == 174 and new_delta['raw_cards_after'] == 148
                by_lang, complete = complete_qualified_names(db)
                assert current_owner_ids <= complete
                owners, stable, restored = classify_old_owners(
                    db, by_lang, complete, current_owner_ids, baseline, r5_eligible)
                restored_raws = {owners[owner_id].raw_value for owner_id in restored}
                assert len(restored_raws) == len(restored) and not restored_raws.intersection(new_raws)
                older_delta, older_album_ids_sha = restored_album_delta(db, restored_raws)
                denominators = {
                    'five_language_literal_raw_title_owners': len(complete),
                    'five_language_literal_raw_title_owner_ids_sha256': canonical_sha256(sorted(complete)),
                    'distinct_album_raw_event_values': db.scalar(select(func.count(func.distinct(KifuAlbum.event)))),
                    'raw_event_owner_rows': db.scalar(select(func.count(KifuRawEventValue.id))),
                }
    current = dict(baseline)
    current['observed_at'] = datetime.now(timezone.utc).isoformat()
    current['baseline_batch_id'] = 595
    current['applied_batch_id'] = 597
    current['raw_event_five_lang_games'] += new_delta['event_after_qualified'] + older_delta['event_after_qualified']
    current['complete_five_lang_raw_games'] += new_delta['raw_cards_after'] + older_delta['raw_cards_after']
    current['complete_five_lang_display_games'] = (current['complete_five_lang_games']
                                                   + current['complete_five_lang_raw_games'])
    for key in ('raw_event_five_lang_games', 'complete_five_lang_raw_games',
                'complete_five_lang_display_games'):
        current[key + '_pct'] = round(100 * current[key] / current['games'], 4)
    current['raw_title_coverage'] = denominators
    current['coverage_method'] = (
        '597后 r6 native：595实际基线 + 597有限174局(148完整卡片) + 旧中文混合 game 校验恢复范围；'
        '恢复范围由精确r5纯函数与r6五语言qualified owner差集确定，仅其public NULL-event棋谱运行strict_slot_approvals。'
        '其他棋谱沿用595基线；未作全库strict扫描。')
    audit = {'environment': 'PROD', 'batch_id': 597, 'read_only': True,
             'r5_raw_event_translation_sha256': NATIVE_SHA256,
             'r6_raw_event_translation_sha256': R6_SHA256,
             'baseline_batch_id': 595,
             'baseline_literal_owner_count': len(stable),
             'new_597_owner_count': len(current_owner_ids),
             'older_restored_owner_count': len(restored),
             'older_restored_owner_ids_sha256': canonical_sha256(sorted(restored)),
             'older_restored_raw_values_sha256': canonical_sha256(sorted(restored_raws)),
             'older_restored_qualified_album_ids_sha256': older_album_ids_sha,
             'new_597_scope': new_delta, 'older_r6_restoration_scope': older_delta,
             'raw_title_coverage': denominators,
             'ledger_targets': {'kifu_raw_event_names': 750, 'kifu_name_research_evidence': 750},
             'global_album_counts_unchanged': {'games': games, 'linked_player_slots': player_links,
                                               'linked_event_games': event_links, 'hidden_games': hidden},
             'note': 'Existing 597 bounded output remains a diagnostic; this adds the exact r5→r6 old-owner delta.'}
    return {'progress': current, 'audit': audit}


if __name__ == '__main__':
    engine = create_engine(os.environ['KATRAIN_DATABASE_URL'],
                           connect_args={'options': '-c default_transaction_read_only=on'})
    try:
        output = report(engine)
    finally:
        engine.dispose()
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
