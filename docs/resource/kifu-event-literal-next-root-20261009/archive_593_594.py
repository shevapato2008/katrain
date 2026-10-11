"""Pack the actual bounded TEST/PROD owner and name evidence without inventories."""

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256


D = Path(__file__).resolve().parent
RESOURCE = D.parent
OUTPUT = RESOURCE / 'kifu-incremental-applied-2026-10-05' / 'kifu-event-literal-593-594-20261009.json.gz'
COMMON = (
    'selection-v2-english150.json', 'source-packet-v2-english150.json',
    'sgf_english-owner-research-unsigned.json', 'sgf_english-name-matrix-unsigned.json',
    'binding-report.json', 'owner-review-request-unsigned.json', 'owner-root-approval.json',
    'owner-plan-execution-approval.json', 'postowner-name-binding-unsigned.json',
    'name-review-request-unsigned.json', 'name-root-approval.json',
    'name-plan-execution-approval.json', 'runtime-compatibility.json',
)
PER_ENV = (
    'capture.json.gz', 'owner-prepare.json.gz', 'owner-dry-run.json.gz',
    'owner-apply.json.gz', 'owner-verify.json.gz', 'postowner-capture.json.gz',
    'name-dry-run.json.gz', 'name-apply.json.gz', 'name-verify.json.gz',
    'name-approved.json', 'http-actual.json',
)
EXTRA = ('594-PROD-progress-actual.json', '594-PROD-bounded-stats.json')
if not __debug__:
    raise RuntimeError('archive assertions must be enabled')


def load(path):
    data = path.read_bytes()
    raw = gzip.decompress(data) if path.suffix == '.gz' else data
    return json.loads(raw), hashlib.sha256(data).hexdigest()


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    source_path = RESOURCE / 'kifu-event-title-next212-source-only-20261009.json'
    source, source_sha = load(source_path)
    common, file_hashes = {}, {source_path.name: source_sha}
    for filename in COMMON:
        common[filename], file_hashes[filename] = load(D / filename)
    assert common['owner-review-request-unsigned.json']['raw_owners'] == 122
    assert common['name-review-request-unsigned.json']['proposed_name_cells'] == 610
    assert common['owner-root-approval.json']['request_canonical_sha256'] == canonical_sha256(
        common['owner-review-request-unsigned.json'])
    assert common['name-root-approval.json']['request_canonical_sha256'] == canonical_sha256(
        common['name-review-request-unsigned.json'])
    environments = {}
    for env in ('TEST', 'PROD'):
        data = {}
        for suffix in PER_ENV:
            filename = f'{env}-{suffix}'
            data[suffix], file_hashes[filename] = load(D / filename)
        assert data['capture.json.gz']['eligible_raw_count'] >= 122
        assert data['postowner-capture.json.gz']['eligible_raw_count'] == 122
        assert data['postowner-capture.json.gz']['current_null_games'] == 938
        assert data['owner-apply.json.gz']['batch_id'] == 593
        assert data['owner-apply.json.gz']['change_count'] == 122
        assert data['owner-verify.json.gz']['verified_owners'] == 122
        assert data['name-apply.json.gz']['batch_id'] == 594
        assert data['name-apply.json.gz']['change_count'] == 1220
        assert data['name-verify.json.gz']['verified_names'] == 610
        assert data['name-verify.json.gz']['verified_ledger_rows'] == 1220
        assert data['http-actual.json']['passed'] and data['http-actual.json']['cases'] == 12
        assert len(data['name-approved.json']['name_bundle']['candidates']) == 610
        assert len(data['name-approved.json']['research_records']) == 610
        assert data['name-approved.json']['approval'] == common['name-root-approval.json']
        assert data['name-apply.json.gz']['bundle_canonical_sha256'] == canonical_sha256(
            data['name-approved.json']['name_bundle'])
        assert file_hashes[f'{env}-capture.json.gz'] == common['owner-review-request-unsigned.json'][
            'capture_file_sha256'][env]
        assert file_hashes[f'{env}-postowner-capture.json.gz'] == common[
            'name-review-request-unsigned.json']['postowner_capture_file_sha256'][env]
        environments[env] = data
    extra = {}
    for filename in EXTRA:
        extra[filename], file_hashes[filename] = load(D / filename)
    stats = extra['594-PROD-progress-actual.json']
    bounded = extra['594-PROD-bounded-stats.json']
    assert stats['applied_batch_id'] == bounded['batch_id'] == 594
    assert stats['complete_five_lang_display_games'] == 43027
    assert stats['raw_event_five_lang_games'] == 39853
    assert bounded['bounded_scope']['games'] == 938
    assert bounded['bounded_scope']['raw_cards_after'] == 567
    inventory_refs = {}
    for env in ('TEST', 'PROD'):
        filename = f'{env}-name-inventory-format4.json.gz'
        path = D / filename
        inventory_refs[env] = {'filename': filename,
                               'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                               'inventory_sha256': environments[env]['postowner-capture.json.gz']['inventory_sha256'],
                               'base_sha256': environments[env]['postowner-capture.json.gz']['base_sha256'],
                               'associations': 173025}
    packet = {
        'archive_format': 'bounded-actual-593-594-v1',
        'assembled_at': datetime.now(timezone.utc).isoformat(),
        'scope': {'owner_batch': 593, 'name_batch': 594, 'raw_owners': 122,
                  'name_cells': 610, 'public_null_event_games': 938,
                  'translation_profile': 'sgf_english', 'formal_event_identity_writes': 0,
                  'album_or_sgf_writes': 0},
        'source_only_reference': {'filename': source_path.name,
                                  'file_sha256': source_sha,
                                  'source_status': source.get('status'),
                                  'selection_source_count': 150},
        'common': common, 'environments': environments,
        'actual_prod_progress': extra,
        'inventory_references_only': inventory_refs,
        'file_sha256': dict(sorted(file_hashes.items())),
        'omitted': ['full format-4 inventory payloads', 'transport tarballs',
                    'unrelated player or formal-event catalog exports'],
    }
    encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    OUTPUT.write_bytes(gzip.compress(encoded, mtime=0))
    print(json.dumps({'archive': OUTPUT.name, 'bytes': OUTPUT.stat().st_size,
                      'file_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                      'owner_batch': 593, 'name_batch': 594,
                      'name_cells': 610, 'games': 938}, ensure_ascii=False))


if __name__ == '__main__':
    main()
