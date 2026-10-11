"""Prepare exact-20 unsigned, source-bound post-591 inputs without DB access.

The root must independently review identity, source registration and generated
rules, then bind a fresh global inventory and sign. This only preserves actual
captures and full 13-field target CAS preimages.
"""
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256

D = Path(__file__).parent
PACKET = D / 'source20-v2.json'
REGISTRY = D / 'source-registry-proposed-pending.json'
GEN = {6635, 4568, 339}
ORIGINAL_LANG = {3771: 'jp', 6642: 'jp', 6635: 'jp', 4568: 'jp',
                 4340: 'jp', 4041: 'jp', 339: 'jp', 3844: 'en', 5351: 'cn',
                 5675: 'tw'}


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


packet = read(PACKET)
registry = read(REGISTRY)
packet_by_prod = {row['prod_player_id']: row for row in packet['players']}
assert len(packet_by_prod) == 20
assert all(len(row['existing_qualified_names']) == 4 for row in packet['players'])
results = {}
for env in ('PROD', 'TEST'):
    cap_path = D / f'{env}-current591-exact20-readonly.json.gz'
    capture = read(cap_path)
    assert capture['source_packet_sha256'] == sha(PACKET)
    rows = {row['prod_player_id']: row for row in capture['rows']}
    assert set(rows) == set(packet_by_prod)
    pending = []
    for prod_id, source in packet_by_prod.items():
        row = rows[prod_id]
        owner = {'kind': 'player', 'id': row['id']}
        assert row['qualified_languages'] == sorted(source['existing_qualified_names'])
        assert row['target_lang'] == source['missing_language']
        assert row['id'] == source['prod_player_id' if env == 'PROD' else 'test_player_id']
        source_lang = ORIGINAL_LANG.get(prod_id, 'cn')
        name = next(name for name in row['all_name_preimages_13_fields'] if name['lang'] == source_lang)
        assert name['display_name'] == source['existing_qualified_names'][source_lang]
        evidence = next(e for e in row['all_owner_evidence_preimages'] if e['id'] == name['evidence_id'])
        found = [check for check in evidence['research_payload']['research']['source_checks']
                 if check['status'] == 'found' and check['candidate_name'] == name['display_name']]
        assert found, (env, prod_id, source_lang)
        anchor = found[0]
        target = row['target_name_preimage']
        assert target is None or len(target) == 13
        entry = {
            'prod_player_id': prod_id,
            'owner': owner,
            'canonical_name': row['owner_preimage']['canonical_name'],
            'target_language': row['target_lang'],
            'proposed_display_name': source['proposed_name'],
            'pending_decision_kind': 'generated' if prod_id in GEN else 'conventional',
            'root_approval_status': 'pending',
            'existing_four_qualified_names': source['existing_qualified_names'],
            'target_name_preimage_13_fields': target,
            'target_name_preimage_sha256': registry_sha256(target) if target is not None else None,
            'target_evidence_preimage': row['target_evidence_preimage'],
            'original_name': name['display_name'],
            'original_source_language': source_lang,
            'original_source_anchor': {
                'url': anchor['url'], 'source_id': anchor['source_id'],
                'body_sha256': anchor['body_sha256'], 'body_excerpt': anchor['body_excerpt'],
                'fetched_at': anchor['fetched_at'], 'http_status': anchor['http_status'],
                'published_name': anchor['candidate_name'],
            },
            'actual_target_sources': source['sources'],
            'source_quality': source['source_quality'],
            'identity_note': source['identity_note'],
            'review_flag': source.get('review_flag'),
            'linked_album_scope_ref': {
                'capture_file': cap_path.name,
                'owner_row_index': list(rows).index(prod_id),
                'owner_game_slots': row['game_slots'],
                'sgf_and_fk_and_rank_fields_captured': True,
            },
        }
        if prod_id in (3771, 6642, 6635, 4568):
            assert target is not None and target['decision_kind'] == 'generated'
            assert 'ko' not in row['qualified_languages']
            entry['proof_repair_of_old_unqualified_generated_row'] = True
        if prod_id == 339:
            entry['japanese_official_full_reading_capture'] = read(D / '339-nihonkiin-profile-capture.json')
            entry['japanese_reading'] = 'ちん はくしょう'
            entry['jstart_korean_publication_role'] = 'actual target-language use, reference tier only; not conventional gate'
        if prod_id == 3844:
            entry['spelling_adjudication'] = {
                'proposed': '亞歷山大·迪那斯塔因',
                'published_variant': '亞歷山大·迪納斯塔因',
                'visible_event_rows_proposed': 3,
                'visible_event_rows_variant': 2,
                'decision_source': 'Astra source-level conditional decision relayed by root; root final review pending',
            }
        pending.append(entry)
    assert len(pending) == len({x['owner']['id'] for x in pending}) == 20
    output = {
        'kind': 'post591_unsigned_pending_mixed20_input',
        'environment': env,
        'status': 'pending_root_source_identity_rule_review',
        'source_packet_file': PACKET.name,
        'source_packet_sha256': sha(PACKET),
        'capture_file': cap_path.name,
        'capture_file_sha256': sha(cap_path),
        'captured_at': capture['captured_at'],
        'source_registry_proposal_file': REGISTRY.name,
        'source_registry_proposal_canonical_sha256': registry_sha256(registry),
        'preceding_batch_id': capture['batch591']['id'],
        'requires_fresh_global_inventory_and_approved_snapshot': True,
        'pending': pending,
    }
    raw = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path = D / f'{env}-post591-unsigned-pending-input.json.gz'
    path.write_bytes(gzip.compress(raw, mtime=0))
    results[env] = {'file': path.name, 'sha256': sha(path),
                    'owners': len(pending), 'game_slots': sum(x['linked_album_scope_ref']['owner_game_slots'] for x in pending)}
(D / 'unsigned-pending-input-manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False))
