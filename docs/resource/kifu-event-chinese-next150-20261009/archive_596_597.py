"""Archive actual 596/597 evidence and corrected r6 progress without full inventories."""

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import canonical_sha256


D = Path(__file__).resolve().parent
RESOURCE = D.parent
OUTPUT = RESOURCE / 'kifu-incremental-applied-2026-10-05' / 'kifu-event-chinese-596-597-20261009.json.gz'
SOURCES = (
    'kifu-event-title-c76-source-only-20261009.json',
    'kifu-event-title-next174-han-source-only-20261009.json',
)
COMMON = (
    'selection.json', 'source-packet.json',
    'sgf_chinese_mixed-owner-research-unsigned.json',
    'sgf_chinese_mixed-name-matrix-unsigned.json', 'binding-report.json',
    'owner-execution-manifest-unsigned.json', 'owner-review-request-unsigned.json',
    'owner-root-approval.json', 'owner-plan-execution-approval.json',
    'postowner-name-binding-unsigned.json', 'name-review-request-unsigned.json',
    'name-root-approval.json', 'name-plan-execution-approval.json',
)
PER_ENV = (
    'capture.json.gz', 'owner-prepare.json.gz', 'owner-dry-run.json.gz',
    'owner-apply.json.gz', 'owner-verify.json.gz', 'postowner-capture.json.gz',
    'name-pending.json', 'name-approved.json', 'name-dry-run.json.gz',
    'name-apply.json.gz', 'name-verify.json.gz', '597-http-actual.json',
    'native-r6-build-actual.json',
)
HELPERS = (
    'owner_inner.py', 'owner_run.py', 'name_inner.py', 'name_run.py',
    'backport_mixed_game.py', '597_bounded_stats.py', '597_bounded_stats_run.py',
    '597_r6_correction.py', '597_r6_correction_run.py', '597_http.py',
    'owner-helper-code-review.md', 'name-helper-code-review.md',
    'bounded-code-review.md',
)
INVENTORIES = {
    'TEST': ('e4edee7eaa08fda0a00d7c6e60d441a5366eec81c031f11db1203e33c9fa81cd',
             7878527, 'f7a702fd82b79237f846f712ec62a3aeb8e66d55c08a47189f286e07f216c23c'),
    'PROD': ('4ce01cb78cc990af35f43f81b06a479b0219eb9582a4cb97930aff1d1eeb7cba',
             7867661, '4f387112f2506f4714d9cf65d4d748bd4248eb1d6da01f4617c28dd0ff07f040'),
}


def read_json(path):
    data = path.read_bytes()
    raw = gzip.decompress(data) if path.suffix == '.gz' else data
    return json.loads(raw), hashlib.sha256(data).hexdigest()


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    source_only = {}
    file_hashes = {}
    for filename in SOURCES:
        source_only[filename], file_hashes[filename] = read_json(RESOURCE / filename)
    common = {}
    for filename in COMMON:
        common[filename], file_hashes[filename] = read_json(D / filename)
    assert common['selection.json']['counts'] == {
        'raw_titles': 150, 'proposed_name_cells': 750, 'saved_inventory_games': 174}
    owner_request = common['owner-review-request-unsigned.json']
    name_request = common['name-review-request-unsigned.json']
    assert owner_request['raw_owners'] == name_request['raw_owners'] == 150
    assert owner_request['current_null_public_games'] == 174
    assert name_request['proposed_name_cells'] == 750
    assert common['owner-root-approval.json']['request_canonical_sha256'] == canonical_sha256(owner_request)
    assert common['name-root-approval.json']['request_canonical_sha256'] == canonical_sha256(name_request)
    assert owner_request['selection_sha256'] == canonical_sha256(common['selection.json'])
    assert owner_request['source_packet_sha256'] == canonical_sha256(common['source-packet.json'])

    environments = {}
    inventory_references = {}
    for env in ('TEST', 'PROD'):
        receipts = {}
        for suffix in PER_ENV:
            filename = f'{env}-{suffix}'
            receipts[suffix], file_hashes[filename] = read_json(D / filename)
        assert receipts['capture.json.gz']['eligible_raw_count'] == 150
        assert receipts['postowner-capture.json.gz']['eligible_raw_count'] == 150
        assert receipts['postowner-capture.json.gz']['current_null_games'] == 174
        assert receipts['owner-apply.json.gz']['batch_id'] == 596
        assert receipts['owner-apply.json.gz']['change_count'] == 150
        assert receipts['owner-verify.json.gz']['verified_owners'] == 150
        assert receipts['name-apply.json.gz']['batch_id'] == 597
        assert receipts['name-apply.json.gz']['change_count'] == 1500
        assert receipts['name-verify.json.gz']['verified_names'] == 750
        assert receipts['name-verify.json.gz']['verified_ledger_rows'] == 1500
        assert receipts['597-http-actual.json']['passed'] is True
        assert receipts['597-http-actual.json']['cases'] == 12
        assert len(receipts['name-approved.json']['name_bundle']['candidates']) == 750
        assert len(receipts['name-approved.json']['research_records']) == 750
        assert receipts['name-approved.json']['approval'] == common['name-root-approval.json']
        assert receipts['name-apply.json.gz']['bundle_canonical_sha256'] == canonical_sha256(
            receipts['name-approved.json']['name_bundle'])
        assert file_hashes[f'{env}-capture.json.gz'] == owner_request['capture_file_sha256'][env]
        assert file_hashes[f'{env}-postowner-capture.json.gz'] == name_request['postowner_capture_file_sha256'][env]
        assert receipts['native-r6-build-actual.json']['verified_files'][
            'katrain/web/kifu/raw_event_translation.py'] == (
                '0aab89aa5a93541dde26381254d3e9ff1a1a1dc6707b6089ba6fd6f473506b1f')
        inventory_file_sha, inventory_bytes, inventory_sha = INVENTORIES[env]
        assert receipts['capture.json.gz']['inventory_sha256'] == inventory_sha
        inventory_references[env] = {
            'filename': f'{env}-name-inventory-format4.json.gz',
            'file_sha256': inventory_file_sha, 'bytes': inventory_bytes,
            'inventory_sha256': inventory_sha,
            'base_sha256': receipts['capture.json.gz']['base_sha256'],
            'associations': 173025,
        }
        environments[env] = receipts

    progress_name = '597-r6-PROD-progress-actual.json'
    audit_name = '597-r6-PROD-correction-audit.json'
    progress, file_hashes[progress_name] = read_json(D / progress_name)
    audit, file_hashes[audit_name] = read_json(D / audit_name)
    assert progress['applied_batch_id'] == audit['batch_id'] == 597
    assert progress['baseline_batch_id'] == audit['baseline_batch_id'] == 595
    assert progress['players_done_count'] == 1723 and progress['events_done_count'] == 64
    assert progress['complete_five_lang_display_games'] == 44314
    assert progress['complete_five_lang_raw_games'] == 32709
    assert progress['raw_event_five_lang_games'] == 41273
    assert audit['read_only'] is True and audit['new_597_owner_count'] == 150
    assert audit['new_597_scope']['games'] == 174
    assert audit['new_597_scope']['raw_cards_after'] == 148
    assert audit['older_restored_owner_count'] == 1241
    assert audit['older_r6_restoration_scope']['eligible_public_null_albums'] == 1246
    assert audit['older_r6_restoration_scope']['raw_cards_after'] == 1059

    helpers = {}
    for filename in HELPERS:
        data = (D / filename).read_bytes()
        helpers[filename] = data.decode('utf-8')
        file_hashes[filename] = hashlib.sha256(data).hexdigest()
    packet = {
        'archive_format': 'bounded-actual-596-597-r6-v1',
        'assembled_at': datetime.now(timezone.utc).isoformat(),
        'scope': {'owner_batch': 596, 'name_batch': 597,
                  'raw_title_owners': 150, 'literal_name_cells': 750,
                  'new_games': 174, 'new_strict_cards': 148,
                  'older_r6_restored_owners': 1241, 'older_restored_games': 1246,
                  'older_restored_strict_cards': 1059,
                  'formal_event_identity_writes': 0, 'album_or_sgf_writes': 0},
        'source_only': source_only, 'common': common, 'environments': environments,
        'actual_prod_progress_r6': progress, 'actual_prod_correction_audit_r6': audit,
        'helper_source_and_reviews': helpers,
        'inventory_references_only': inventory_references,
        'file_sha256': dict(sorted(file_hashes.items())),
        'omitted': ['full format-4 inventory payloads', 'transport tarballs',
                    'diagnostic 597-PROD-progress-actual.json',
                    'unrelated player or formal-event catalog exports'],
    }
    encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    OUTPUT.write_bytes(gzip.compress(encoded, mtime=0))
    print(json.dumps({'archive': OUTPUT.name, 'bytes': OUTPUT.stat().st_size,
                      'file_sha256': hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                      'owner_batch': 596, 'name_batch': 597, 'new_games': 174,
                      'complete_five_lang_display_games': 44314}, ensure_ascii=False))


if __name__ == '__main__':
    main()
