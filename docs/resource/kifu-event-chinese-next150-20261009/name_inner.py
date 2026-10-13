"""Root-only native name dry-run, guarded apply, and read-only verification."""

from contextlib import contextmanager
from copy import deepcopy
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import Column, String, create_engine, inspect, select, text

from katrain.web.core.models_db import (
    KifuAlbum, KifuNameBatch, KifuNameChange, KifuNameResearchEvidence,
    KifuRawEventName, KifuRawEventValue,
)
from katrain.web.kifu.name_batch import _catalog_sha, _image, _snapshot_parts, apply_bundle, batch_status, dry_run_bundle
from katrain.web.kifu.name_candidates import canonical_sha256, validate_bundle
from katrain.web.kifu.name_inventory import ALBUM_COLUMNS
from katrain.web.kifu.raw_event_translation import eligible_literal_raw_name


if not __debug__:
    raise RuntimeError('name guard assertions must be enabled')
D = Path('/work')
IMAGE_IDS = {
    'TEST': 'sha256:82124209ad6425190d587fec10b06eb7cab8b80067cd345cc523bd9a760523c4',
    'PROD': 'sha256:6eb7597b5b478c082fe91405c0223531a46380bf53b9d7dc33e8e74cfb642b02',
}
MANIFEST = json.loads((D / 'sgf_chinese_mixed-owner-research-unsigned.json').read_text())
MATRIX = json.loads((D / 'sgf_chinese_mixed-name-matrix-unsigned.json').read_text())
SELECTION = json.loads((D / 'selection.json').read_text())
SOURCE_PACKET = json.loads((D / 'source-packet.json').read_text())
assert MATRIX['owner_manifest_canonical_sha256'] == canonical_sha256(MANIFEST)
assert MATRIX['source_packet_canonical_sha256'] == MANIFEST['source_packet_sha256']
assert canonical_sha256(SELECTION) == MANIFEST['selection_sha256']
assert canonical_sha256(SOURCE_PACKET) == MANIFEST['source_packet_sha256']


def json_gz(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def physical_image(row):
    image = {key: value.isoformat() if hasattr(value, 'isoformat') else value for key, value in row.items()}
    image['sgf_content'] = {'sha256': hashlib.sha256((row['sgf_content'] or '').encode()).hexdigest()}
    return image


def patch_native_album(conn):
    physical = {column['name']: column for column in inspect(conn).get_columns('kifu_albums')}
    hidden = physical.get('list_hidden_reason')
    assert hidden is not None and isinstance(hidden['type'], String) and hidden['type'].length == 64
    assert 'event_edition_id' in physical
    inventory_columns = tuple(column.key for column in ALBUM_COLUMNS)
    if 'list_hidden_reason' not in KifuAlbum.__table__.c:
        KifuAlbum.list_hidden_reason = Column(String(64), nullable=True)
    assert tuple(column.key for column in ALBUM_COLUMNS) == inventory_columns
    assert 'list_hidden_reason' not in inventory_columns and 'event_edition_id' not in inventory_columns


def load_inputs(environment):
    request = json.loads((D / 'name-review-request-unsigned.json').read_text())
    approval = json.loads((D / 'name-root-approval.json').read_text())
    pending = json.loads((D / f'{environment}-name-pending.json').read_text())
    approved = json.loads((D / f'{environment}-name-approved.json').read_text())
    capture_path = D / f'{environment}-postowner-capture.json.gz'
    capture = json_gz(capture_path)
    inventory = json_gz(D / f'{environment}-name-inventory-format4.json.gz')
    assert request['status'] == 'pending_independent_root_name_review'
    assert request['producer_id'] == '/root/next_chinese_event_native_prep'
    assert request['producer_model'] == 'gpt-6-sol'
    assert request['raw_owners'] == 150 and request['proposed_name_cells'] == 750
    assert request['source_matrix_canonical_sha256'] == canonical_sha256(MATRIX)
    assert request['owner_manifest_canonical_sha256'] == canonical_sha256(MANIFEST)
    assert approval['status'] == 'approved_literal_name_review' and approval['allow_name_assembly'] is True
    assert approval['reviewer_id'] == '/root' and approval['reviewer_id'] != request['producer_id']
    assert approval['request_canonical_sha256'] == canonical_sha256(request)
    assert pending['environment'] == approved['environment'] == capture['environment'] == environment
    assert canonical_sha256(pending) == request['pending_artifact_canonical_sha256'][environment]
    assert approved['approval'] == approval and approved['status'] == 'root_reviewed_name_bundle'
    expected = deepcopy(pending)
    for candidate in expected['name_bundle']['candidates']:
        assert candidate['review_status'] == 'pending'
        candidate.update({'review_status': 'approved', 'reviewer_id': approval['reviewer_id'],
                          'reviewer_model': approval['reviewer_model'],
                          'reviewed_at': approval['reviewed_at'],
                          'review_conclusion': approval['review_conclusion']})
    expected['status'] = 'root_reviewed_name_bundle'
    expected['approval'] = approval
    assert approved == expected
    assert (pending['source_matrix_canonical_sha256']
            == approved['source_matrix_canonical_sha256'] == canonical_sha256(MATRIX))
    assert capture['status'] == 'post_owner_read_only' and capture['ready_for_unsigned_name_review']
    assert capture['raw_count_requested'] == capture['eligible_raw_count'] == 150
    assert capture['current_null_games'] == 174
    assert capture['selection_sha256'] == MANIFEST['selection_sha256']
    assert capture['source_packet_sha256'] == MANIFEST['source_packet_sha256']
    assert capture['owner_manifest_sha256'] == canonical_sha256(MANIFEST)
    assert capture['frozen_preowner_capture_file_sha256'] == MATRIX['capture_file_sha256'][environment]
    assert hashlib.sha256(capture_path.read_bytes()).hexdigest() == request['postowner_capture_file_sha256'][environment]
    assert approved['postowner_capture_file_sha256'] == request['postowner_capture_file_sha256'][environment]
    bundle = approved['name_bundle']
    assert bundle['bundle_format'] == 2 and bundle['inventory_format'] == 4
    assert inventory['inventory_format'] == 4
    assert len(bundle['owners']) == 150 and len(bundle['candidates']) == len(approved['research_records']) == 750
    assert len(bundle['members']) == 750 and not bundle['album_links']
    assert all(candidate['name_preimage_sha256'] is None for candidate in bundle['candidates'])
    assert all(record['original_language'] == 'zh-Hans'
               and record['sgf_literal_evidence']['owner_profile'] == 'sgf_chinese_mixed'
               for record in approved['research_records'])
    registry_row = capture['latest_registry']
    assert approved['registry'] == registry_row['registry']
    assert registry_row['version'] == approved['registry']['version']
    assert 0 < len(registry_row['version']) <= 64
    assert len(registry_row['sha256']) == 64
    assert inventory['sha256'] == bundle['inventory_sha256'] == capture['inventory_sha256']
    assert inventory['base_sha256'] == capture['base_sha256']
    assert inventory['event_selection'] == capture['selection_supplement']
    assert bundle['catalog_sha256'] == capture['catalog_sha256']
    report = validate_bundle(bundle, approved['registry'], inventory, approved['research_records'])
    assert report['ready'] and report['write_ready'] and report['approved'] == 750 and not report['errors']
    return request, approval, approved, capture, inventory


def scoped_guard(conn, approved, capture, *, before):
    bundle = approved['name_bundle']
    by_raw = {row['raw_value']: row for row in capture['records']}
    assert len(by_raw) == 150
    ids = []
    for declaration in bundle['owners']:
        raw = declaration['preimage']['raw_value']
        source = by_raw[raw]
        owner_id = declaration['owner']['id']
        assert _image(conn, KifuRawEventValue.__table__, owner_id) == declaration['preimage'] == source['owner']
        rows = conn.execute(text('SELECT * FROM kifu_albums WHERE event=:raw ORDER BY id'),
                            {'raw': raw}).mappings().all()
        assert [row['id'] for row in rows] == declaration['occurrence_album_ids'] == source['album_ids']
        assert canonical_sha256([physical_image(row) for row in rows]) == source['full_physical_album_sha256']
        ids.extend(row['id'] for row in rows)
        if before:
            assert not source['name_preimages'] and not source['evidence_preimages']
            assert not conn.execute(select(KifuRawEventName.id).where(
                KifuRawEventName.raw_event_id == owner_id).limit(1)).first()
            assert not conn.execute(select(KifuNameResearchEvidence.id).where(
                KifuNameResearchEvidence.raw_event_id == owner_id).limit(1)).first()
    assert len(ids) == len(set(ids)) == 174
    hidden_count = conn.scalar(text('SELECT COUNT(*) FROM kifu_albums WHERE list_hidden_reason IS NOT NULL'))
    assert hidden_count == 250
    inventory_sha, supplement, base = _snapshot_parts(conn, inventory_format=4)
    assert (inventory_sha, base, supplement) == (capture['inventory_sha256'], capture['base_sha256'],
                                                  capture['selection_supplement'])
    assert _catalog_sha(conn) == bundle['catalog_sha256']
    return {'album_count': 174, 'album_ids_sha256': canonical_sha256(sorted(ids)),
            'hidden_album_count': hidden_count,
            'inventory_sha256': inventory_sha, 'catalog_sha256': bundle['catalog_sha256'],
            'scope_physical_sha256': canonical_sha256({raw: by_raw[raw]['full_physical_album_sha256']
                                                       for raw in sorted(by_raw)})}


def execution_approval(environment, request, approved):
    execution = json.loads((D / 'name-plan-execution-approval.json').read_text())
    assert execution['status'] == 'approved_name_bundle_execution'
    assert execution['allow_apply'] is True and execution['reviewer_id'] == '/root'
    assert execution['reviewer_model'] and execution['reviewed_at'] and execution['review_conclusion']
    assert execution['request_canonical_sha256'] == canonical_sha256(request)
    pins = execution['environments'][environment]
    assert pins['image_id'] == IMAGE_IDS[environment]
    assert pins['approved_artifact_canonical_sha256'] == canonical_sha256(approved)
    assert pins['bundle_canonical_sha256'] == canonical_sha256(approved['name_bundle'])
    dry = json_gz(D / f'{environment}-name-dry-run.json.gz')
    assert dry['phase'] == 'dry-run' and dry['environment'] == environment
    assert dry['status'] == 'read_only_ready' and dry['report']['ready'] and dry['report']['write_ready']
    assert dry['report']['bundle_sha256'] == pins['bundle_canonical_sha256']
    return pins, dry


def verify_names(conn, approved, batch_id):
    bundle = approved['name_bundle']
    batch = _image(conn, KifuNameBatch.__table__, batch_id)
    assert batch is not None and batch['status'] == 'applied'
    assert batch['bundle_sha256'] == canonical_sha256(bundle)
    assert batch['reviewed_artifact']['bundle'] == bundle
    assert batch['reviewed_artifact']['research_hashes'] == sorted(
        canonical_sha256(record) for record in approved['research_records'])
    changes = conn.execute(select(KifuNameChange.__table__).where(
        KifuNameChange.batch_id == batch_id)).mappings().all()
    assert len(changes) == 1500
    assert {row['target_table'] for row in changes} == {'kifu_raw_event_names', 'kifu_name_research_evidence'}
    tables = {'kifu_raw_event_names': KifuRawEventName.__table__,
              'kifu_name_research_evidence': KifuNameResearchEvidence.__table__}
    assert all(row['before_image'] is None
               and _image(conn, tables[row['target_table']], row['target_row_id']) == row['after_image']
               for row in changes)
    for candidate in bundle['candidates']:
        owner_id = candidate['owner']['id']
        name = conn.execute(select(KifuRawEventName.__table__).where(
            KifuRawEventName.raw_event_id == owner_id,
            KifuRawEventName.lang == candidate['lang'])).mappings().one()
        name = _image(conn, KifuRawEventName.__table__, name['id'])
        evidence = _image(conn, KifuNameResearchEvidence.__table__, name['evidence_id'])
        owner = _image(conn, KifuRawEventValue.__table__, owner_id)
        assert name['display_name'] == candidate['display_name'] and name['status'] == 'verified'
        assert evidence['research_payload']['candidate'] == candidate
        assert eligible_literal_raw_name(name, evidence, owner)
    return {'verified_names': 750, 'verified_ledger_rows': 1500}


def main():
    environment, phase = sys.argv[1:]
    assert environment in IMAGE_IDS and phase in {'dry-run', 'apply', 'verify'}
    request, approval, approved, capture, inventory = load_inputs(environment)
    bundle, registry, research = approved['name_bundle'], approved['registry'], approved['research_records']
    if phase == 'apply':
        pins, dry = execution_approval(environment, request, approved)
        engine = create_engine(os.environ['KATRAIN_DATABASE_URL'])
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            patch_native_album(conn)
        import katrain.web.kifu.name_batch as name_batch
        original_lock = name_batch._locked_write

        @contextmanager
        def guarded_lock(target_engine):
            with original_lock(target_engine) as conn:
                assert scoped_guard(conn, approved, capture, before=False) == dry['scoped_guard']
                previous = conn.execute(select(KifuNameBatch.__table__).where(
                    KifuNameBatch.bundle_sha256 == pins['bundle_canonical_sha256'])).mappings().one_or_none()
                if previous is None:
                    assert scoped_guard(conn, approved, capture, before=True) == dry['scoped_guard']
                else:
                    verify_names(conn, approved, previous['id'])
                yield conn

        name_batch._locked_write = guarded_lock
        try:
            result = name_batch.apply_bundle(engine, bundle, registry, inventory, research,
                                             expected_bundle_sha256=pins['bundle_canonical_sha256'])
        finally:
            name_batch._locked_write = original_lock
            engine.dispose()
        assert ((result['status'] == 'applied' and result['change_count'] == 1500)
                or (result['status'] == 'already_applied' and result['change_count'] == 0))
        output = {'phase': phase, 'environment': environment, 'status': result['status'],
                  'batch_id': result['batch_id'], 'change_count': result['change_count'],
                  'bundle_canonical_sha256': pins['bundle_canonical_sha256']}
    else:
        engine = create_engine(os.environ['KATRAIN_DATABASE_URL'],
                               connect_args={'options': '-c default_transaction_read_only=on'})
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            patch_native_album(conn)
            guard = scoped_guard(conn, approved, capture, before=phase == 'dry-run')
            if phase == 'dry-run':
                report = dry_run_bundle(engine, bundle, registry, inventory, research,
                                        expected_bundle_sha256=canonical_sha256(bundle))
                assert report['ready'] and report['write_ready'] and report['candidate_count'] == 750
                assert len(report['affected_albums']) == 174
                output = {'phase': phase, 'environment': environment, 'status': 'read_only_ready',
                          'report': report, 'scoped_guard': guard,
                          'bundle_canonical_sha256': canonical_sha256(bundle)}
            else:
                applied = json_gz(D / f'{environment}-name-apply.json.gz')
                assert applied['status'] in {'applied', 'already_applied'}
                status = batch_status(engine, applied['batch_id'])
                assert status['status'] == 'applied' and status['bundle_sha256'] == canonical_sha256(bundle)
                checks = verify_names(conn, approved, applied['batch_id'])
                output = {'phase': phase, 'environment': environment, 'status': 'verified',
                          'batch_id': applied['batch_id'], 'bundle_canonical_sha256': canonical_sha256(bundle),
                          'scoped_guard': guard, **checks}
        engine.dispose()
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
