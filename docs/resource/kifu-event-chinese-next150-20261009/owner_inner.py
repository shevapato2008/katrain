"""Native admin owner-only prepare, dry-run, root-gated apply, and verify.

Apply requires an additional root-signed execution approval and uses the
reviewed public apply_plan, lock, inspect, journal and CAS unchanged.
"""

from contextlib import contextmanager
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import Column, String, create_engine, inspect, select, text

from katrain.core.sgf_parser import SGF
from katrain.web.core.models_db import (
    KifuAlbum, KifuAlbumEventSelection, KifuNameBatch, KifuNameChange, KifuNameResearchEvidence,
    KifuNameSourceRegistry, KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_batch import _OWNER, _image, _snapshot_parts
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_inventory import ALBUM_COLUMNS

from capture import root_fragment


if not __debug__:
    raise RuntimeError('owner guard assertions must be enabled')

D = Path('/work')
PROFILE = 'sgf_chinese_mixed'
IMAGE_IDS = {
    'TEST': 'sha256:82124209ad6425190d587fec10b06eb7cab8b80067cd345cc523bd9a760523c4',
    'PROD': 'sha256:6eb7597b5b478c082fe91405c0223531a46380bf53b9d7dc33e8e74cfb642b02',
}
REQUEST = json.loads((D / 'owner-review-request-unsigned.json').read_text())
MANIFEST = json.loads((D / 'sgf_chinese_mixed-owner-research-unsigned.json').read_text())
MATRIX = json.loads((D / 'sgf_chinese_mixed-name-matrix-unsigned.json').read_text())
assert REQUEST['status'] == 'pending_independent_root_review'
assert REQUEST['manifest_canonical_sha256'] == canonical_sha256(MANIFEST)
assert REQUEST['name_matrix_canonical_sha256'] == canonical_sha256(MATRIX)
assert MANIFEST['profile'] == MATRIX['profile'] == PROFILE
assert MANIFEST['raw_value_count'] == MATRIX['raw_titles'] == 150
assert MANIFEST['current_null_games'] == MATRIX['current_games'] == 174
assert MATRIX['proposed_name_cells'] == 750
assert REQUEST['producer_id'] == '/root/next_chinese_event_native_prep'
assert REQUEST['producer_model'] == 'gpt-6-sol'
assert REQUEST['produced_at'] == MANIFEST['assembled_at']
assert REQUEST['profile'] == PROFILE
assert REQUEST['raw_owners'] == 150 and REQUEST['current_null_public_games'] == 174
assert REQUEST['proposed_name_cells_for_later_phase'] == 750
assert REQUEST['selection_sha256'] == MANIFEST['selection_sha256']
assert REQUEST['source_packet_sha256'] == MANIFEST['source_packet_sha256']
assert REQUEST['native_importer_image_id'] == IMAGE_IDS
assert MATRIX['owner_manifest_canonical_sha256'] == canonical_sha256(MANIFEST)
assert MATRIX['source_packet_canonical_sha256'] == MANIFEST['source_packet_sha256']
assert MATRIX['capture_file_sha256'] == REQUEST['capture_file_sha256']


def image(row):
    return {key: value.isoformat() if hasattr(value, 'isoformat') else value
            for key, value in row.items()}


def patch_native_album(conn):
    """Map only the physical hidden column; keep native inventory columns fixed."""
    physical = {column['name']: column for column in inspect(conn).get_columns('kifu_albums')}
    hidden = physical.get('list_hidden_reason')
    assert hidden is not None and isinstance(hidden['type'], String) and hidden['type'].length == 64
    assert 'event_edition_id' in physical
    before = tuple(column.key for column in ALBUM_COLUMNS)
    if 'list_hidden_reason' not in KifuAlbum.__table__.c:
        KifuAlbum.list_hidden_reason = Column(String(64), nullable=True)
    assert tuple(column.key for column in ALBUM_COLUMNS) == before
    assert 'list_hidden_reason' not in before and 'event_edition_id' not in before
    return sorted(set(physical) & {'list_hidden_reason', 'event_edition_id'})


def scoped_guard(conn, environment, capture, *, before):
    """Recheck exact 174 original records and current 750-name collision boundary."""
    raw_records = {row['raw_value']: row for row in capture['records']}
    members = {row['raw_value']: row for row in MANIFEST['member_manifest'][environment]['members']}
    proposals = {row['raw_value']: row for row in MATRIX['records']}
    assert set(members) == set(proposals) and len(members) == 150
    all_ids = []
    full_images = []
    for raw in sorted(members):
        source = raw_records[raw]
        member = members[raw]
        # The native importer model may omit newer physical columns. Bound the
        # complete physical album image, including every FK and visibility field.
        rows = conn.execute(text('SELECT * FROM kifu_albums WHERE event=:raw ORDER BY id'),
                            {'raw': raw}).mappings().all()
        ids = [row['id'] for row in rows]
        assert ids == member['album_ids'] == source['album_ids']
        scope = []
        refs = []
        raw_full_images = []
        for row in rows:
            assert row['event_id'] is None and row['duplicate_of_id'] is None
            assert row['list_hidden_reason'] is None and row['event_edition_id'] is None
            sgf_sha = hashlib.sha256((row['sgf_content'] or '').encode('utf-8')).hexdigest()
            props = dict(SGF.parse_sgf(root_fragment(row['sgf_content'])).properties)
            assert props.get('GN', [None])[0] == raw and props.get('EV', []) == []
            refs.append({'album_id': row['id'], 'source_path': row['source_path'],
                         'sgf_sha256': sgf_sha, 'gn_values': props['GN'], 'ev_values': []})
            scope.append({'id': row['id'], 'event': row['event'], 'event_id': row['event_id'],
                          'round_name': row['round_name'], 'date_played': row['date_played'],
                          'black_rank': row['black_rank'], 'white_rank': row['white_rank'],
                          'source_path': row['source_path'], 'sgf_sha256': sgf_sha})
            full = image(row)
            full['sgf_content'] = {'sha256': sgf_sha}
            full_images.append(full)
            raw_full_images.append(full)
        assert scope == member['scope_rows'] == source['scope_rows']
        assert refs == source['original_sgf_refs']
        assert canonical_sha256(scope) == member['scope_sha256'] == source['scope_sha256']
        assert canonical_sha256(raw_full_images) == source['full_physical_album_sha256']
        all_ids.extend(ids)
        owner = next(record['owners'][environment]['preimage'] for record in MANIFEST['records']
                     if record['raw_value'] == raw)
        current = _image(conn, KifuRawEventValue.__table__, owner['id'])
        assert current is not None and current['raw_value'] == raw
        exact_owners = conn.execute(select(KifuRawEventValue.id).where(
            KifuRawEventValue.raw_value == raw)).scalars().all()
        assert exact_owners == [owner['id']]
        assert current['category'] == 'unclassified_pending'
        assert current['review_status'] in {'pending', 'approved'}
        if before:
            assert current == owner == source['owner']
        assert not conn.execute(select(KifuRawEventName.id).where(
            KifuRawEventName.raw_event_id == owner['id']).limit(1)).first()
        assert not conn.execute(select(KifuNameResearchEvidence.id).where(
            KifuNameResearchEvidence.raw_event_id == owner['id']).limit(1)).first()
    assert len(all_ids) == len(set(all_ids)) == 174
    selected = conn.execute(select(KifuAlbumEventSelection.album_id).where(
        (KifuAlbumEventSelection.album_id.in_(all_ids)) |
        (KifuAlbumEventSelection.selected_raw.in_(list(members)))).limit(1)).first()
    assert selected is None
    proposal_keys = {(lang, normalize_alias(name)): raw for raw, row in proposals.items()
                     for lang, name in row['names'].items()}
    assert len(proposal_keys) == 750
    collisions = []
    for kind, (_owner_model, name_model, owner_column) in _OWNER.items():
        for existing in conn.execute(select(name_model.__table__).where(
                name_model.lang.in_(['cn', 'tw', 'jp', 'ko', 'en']),
                name_model.status == 'verified')).mappings():
            key = (existing['lang'], normalize_alias(existing['display_name']))
            if key in proposal_keys:
                collisions.append([proposal_keys[key], key[0], kind, existing[owner_column]])
    assert not collisions, collisions[:5]
    return {'album_count': len(all_ids), 'album_ids_sha256': canonical_sha256(sorted(all_ids)),
            'full_physical_album_sha256': canonical_sha256(full_images),
            'name_collision_count': 0, 'physical_extra_fields': ['event_edition_id', 'list_hidden_reason']}


def read_capture(environment):
    path = D / f'{environment}-capture.json.gz'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == REQUEST['capture_file_sha256'][environment]
    result = json.loads(gzip.decompress(path.read_bytes()))
    assert result['environment'] == environment and result['raw_count_requested'] == 150
    assert result['eligible_raw_count'] == 150 and result['current_null_games'] == 174
    assert not result['rejections'] and not result['external_collisions']
    assert result['selection_sha256'] == MANIFEST['selection_sha256']
    assert result['source_packet_sha256'] == MANIFEST['source_packet_sha256']
    assert result['inventory_sha256'] == MANIFEST['member_manifest'][environment]['inventory_sha256']
    return result


def read_approval():
    approval = json.loads((D / 'owner-root-approval.json').read_text())
    assert approval['status'] == 'approved_owner_review'
    assert approval['request_canonical_sha256'] == canonical_sha256(REQUEST)
    assert approval['manifest_canonical_sha256'] == REQUEST['manifest_canonical_sha256']
    assert approval['name_matrix_canonical_sha256'] == REQUEST['name_matrix_canonical_sha256']
    assert approval['reviewer_id'] == '/root' and approval['reviewer_id'] != REQUEST['producer_id']
    assert approval['reviewer_model'] and approval['reviewed_at'] and approval['review_conclusion']
    return approval


def apply_only(environment, capture):
    """Check root execution approval, then add one guard inside the original lock."""
    execution = json.loads((D / 'owner-plan-execution-approval.json').read_text())
    assert execution['status'] == 'approved_owner_plan_execution'
    assert execution['allow_apply'] is True and execution['reviewer_id'] == '/root'
    assert execution['reviewer_model'] and execution['reviewed_at'] and execution['review_conclusion']
    pins = execution['environments'][environment]
    assert pins['image_id'] == IMAGE_IDS[environment]
    assert pins['manifest_canonical_sha256'] == canonical_sha256(MANIFEST)
    prepared = json.loads(gzip.decompress((D / f'{environment}-owner-prepare.json.gz').read_bytes()))
    plan = prepared['plan']
    assert prepared['phase'] == 'prepare' and prepared['environment'] == environment
    assert prepared['manifest_canonical_sha256'] == pins['manifest_canonical_sha256']
    assert prepared['plan_canonical_sha256'] == pins['plan_canonical_sha256'] == canonical_sha256(plan)
    assert plan['inventory_sha256'] == capture['inventory_sha256']
    dry = json.loads(gzip.decompress((D / f'{environment}-owner-dry-run.json.gz').read_bytes()))
    assert dry['phase'] == 'dry-run' and dry['environment'] == environment
    assert dry['status'] == 'read_only_ready' and dry['plan_canonical_sha256'] == pins['plan_canonical_sha256']
    assert dry['report'] == {'ready': True, 'raw_owners': 150, 'albums': 174,
                             'name_writes': 0, 'fk_writes': 0}
    assert dry['scoped_guard'] == prepared['scoped_guard']
    engine = create_engine(os.environ['KATRAIN_DATABASE_URL'])
    with engine.connect() as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        assert patch_native_album(conn) == ['event_edition_id', 'list_hidden_reason']
    import scripts.kifu_raw_event_title_owners as owner_tool
    original_locked_write = owner_tool._locked_write

    @contextmanager
    def guarded_locked_write(target_engine):
        with original_locked_write(target_engine) as conn:
            # Native apply_plan checks exact before/after images under this
            # same lock, including recovery of an already committed plan.
            assert scoped_guard(conn, environment, capture, before=False) == prepared['scoped_guard']
            yield conn

    owner_tool._locked_write = guarded_locked_write
    try:
        applied = owner_tool.apply_plan(
            engine, plan, prepared['registry'], pins['manifest_canonical_sha256'],
            pins['plan_canonical_sha256'], profile=PROFILE, manifest=MANIFEST)
    finally:
        owner_tool._locked_write = original_locked_write
        engine.dispose()
    assert applied['status'] in {'applied', 'already_applied'}
    return {'phase': 'apply', 'environment': environment, 'status': applied['status'],
            'batch_id': applied['batch_id'], 'change_count': applied['change_count'],
            'plan_canonical_sha256': pins['plan_canonical_sha256'],
            'manifest_canonical_sha256': pins['manifest_canonical_sha256'],
            'scoped_guard_sha256': canonical_sha256(prepared['scoped_guard'])}


def main():
    environment, phase = sys.argv[1:]
    assert environment in {'TEST', 'PROD'} and phase in {'prepare', 'dry-run', 'apply', 'verify'}
    approval = read_approval() if phase == 'prepare' else None
    capture = read_capture(environment)
    if phase == 'apply':
        result = apply_only(environment, capture)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
        return
    engine = create_engine(os.environ['KATRAIN_DATABASE_URL'],
                           connect_args={'options': '-c default_transaction_read_only=on'})
    with engine.connect() as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        physical = patch_native_album(conn)
        assert physical == ['event_edition_id', 'list_hidden_reason']
        current_guard = scoped_guard(conn, environment, capture, before=phase != 'verify')
    from scripts.kifu_raw_event_title_owners import inspect_plan, prepare_plan
    if phase == 'prepare':
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            latest = conn.execute(select(KifuNameSourceRegistry.__table__).order_by(
                KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one()
            registry = latest['registry']
            assert registry_sha256(registry) == latest['sha256']
        plan = prepare_plan(engine, MANIFEST, environment, registry,
                            producer_id=REQUEST['producer_id'], producer_model=REQUEST['producer_model'],
                            produced_at=REQUEST['produced_at'], reviewer_id=approval['reviewer_id'],
                            reviewer_model=approval['reviewer_model'], reviewed_at=approval['reviewed_at'],
                            review_conclusion=approval['review_conclusion'], profile=PROFILE)
        assert plan['inventory_sha256'] == capture['inventory_sha256']
        assert plan['raw_count'] == 150 and plan['game_total'] == 174 and len(plan['changes']) == 150
        result = {'phase': phase, 'environment': environment, 'status': 'prepared_for_root_plan_review',
                  'plan': plan, 'registry': registry, 'scoped_guard': current_guard,
                  'manifest_canonical_sha256': canonical_sha256(MANIFEST),
                  'plan_canonical_sha256': canonical_sha256(plan)}
    else:
        prepared = json.loads(gzip.decompress((D / f'{environment}-owner-prepare.json.gz').read_bytes()))
        assert prepared['environment'] == environment and prepared['phase'] == 'prepare'
        plan = prepared['plan']
        assert prepared['plan_canonical_sha256'] == canonical_sha256(plan)
        assert prepared['manifest_canonical_sha256'] == canonical_sha256(MANIFEST)
        assert current_guard == prepared['scoped_guard']
        if phase == 'dry-run':
            with engine.connect() as conn:
                conn.execute(text('SET TRANSACTION READ ONLY'))
                report = inspect_plan(conn, plan, prepared['registry'],
                                      prepared['manifest_canonical_sha256'],
                                      profile=PROFILE, manifest=MANIFEST)
            assert report == {'ready': True, 'raw_owners': 150, 'albums': 174,
                              'name_writes': 0, 'fk_writes': 0}
            result = {'phase': phase, 'environment': environment, 'status': 'read_only_ready',
                      'report': report, 'plan_canonical_sha256': prepared['plan_canonical_sha256'],
                      'scoped_guard': current_guard}
        else:
            with engine.connect() as conn:
                conn.execute(text('SET TRANSACTION READ ONLY'))
                for change in plan['changes']:
                    assert _image(conn, KifuRawEventValue.__table__, change['after']['id']) == change['after']
                batch = conn.execute(select(KifuNameBatch.__table__).where(
                    KifuNameBatch.bundle_sha256 == prepared['plan_canonical_sha256'])).mappings().one()
                assert batch['status'] == 'applied' and batch['reviewed_artifact']['bundle'] == plan
                journal = conn.execute(select(KifuNameChange.__table__).where(
                    KifuNameChange.batch_id == batch['id']).order_by(KifuNameChange.sequence)).mappings().all()
                assert len(journal) == 150
                assert all(row['target_table'] == 'kifu_raw_event_values' for row in journal)
                inventory_sha, _, _ = _snapshot_parts(conn, inventory_format=4)
                assert inventory_sha == plan['inventory_sha256']
            result = {'phase': phase, 'environment': environment, 'status': 'verified_after_root_apply',
                      'verified_owners': 150, 'unchanged_albums': 174, 'name_writes': 0, 'fk_writes': 0,
                      'inventory_sha256': inventory_sha,
                      'plan_canonical_sha256': prepared['plan_canonical_sha256'],
                      'scoped_guard': current_guard}
    engine.dispose()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
