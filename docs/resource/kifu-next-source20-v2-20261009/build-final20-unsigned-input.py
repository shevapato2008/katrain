"""Bind final source 20 to read-only 591 owner snapshots, without approval."""
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256

D = Path(__file__).parent
packet_path = D / 'source20-post591-final-pending.json'
packet = json.loads(packet_path.read_text())
registry_path = D / 'source-registry-proposed-pending.json'
registry = json.loads(registry_path.read_text())
replacement = next(row for row in packet['players'] if row['prod_player_id'] == 696)
result = {}


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for env in ('PROD', 'TEST'):
    old_path = D / f'{env}-post591-unsigned-pending-input.json.gz'
    old = read(old_path)
    old_scope = {row['prod_player_id']: row for row in old['pending'] if row['prod_player_id'] != 339}
    assert len(old_scope) == 19
    cap_path = D / f'{env}-replacement696-current591-readonly.json.gz'
    cap = read(cap_path)
    assert cap['batch591']['id'] == 591 and len(cap['rows']) == 1
    row = cap['rows'][0]
    assert row['prod_player_id'] == 696 and row['target_lang'] == 'ko'
    assert row['qualified_languages'] == ['cn', 'en', 'jp', 'tw']
    cn = next(name for name in row['all_name_preimages_13_fields'] if name['lang'] == 'cn')
    assert cn['display_name'] == '高若环'
    evidence = next(item for item in row['all_owner_evidence_preimages'] if item['id'] == cn['evidence_id'])
    anchor = next(check for check in evidence['research_payload']['research']['source_checks']
                  if check['status'] == 'found' and check['candidate_name'] == '高若环')
    target = row['target_name_preimage']
    assert target is not None and len(target) == 13 and target['status'] == 'review'
    assert target['display_name'] == '고 약환' and target['evidence_id'] is None
    new = {
        'prod_player_id': 696,
        'owner': {'kind': 'player', 'id': row['id']},
        'canonical_name': row['owner_preimage']['canonical_name'],
        'target_language': 'ko',
        'proposed_display_name': '가오뤄환',
        'pending_decision_kind': 'conventional',
        'root_approval_status': 'pending',
        'existing_four_qualified_names': replacement['existing_qualified_names'],
        'target_name_preimage_13_fields': target,
        'target_name_preimage_sha256': registry_sha256(target),
        'target_evidence_preimage': row['target_evidence_preimage'],
        'original_name': cn['display_name'],
        'original_source_language': 'cn',
        'original_source_anchor': {
            'url': anchor['url'], 'source_id': anchor['source_id'],
            'body_sha256': anchor['body_sha256'], 'body_excerpt': anchor['body_excerpt'],
            'fetched_at': anchor['fetched_at'], 'http_status': anchor['http_status'],
            'published_name': anchor['candidate_name'],
        },
        'actual_target_sources': replacement['sources'],
        'source_quality': replacement['source_quality'],
        'identity_note': replacement['identity_note'],
        'review_flag': replacement['review_flag'],
        'linked_album_scope_ref': {
            'capture_file': cap_path.name,
            'capture_file_sha256': sha(cap_path),
            'owner_row_index': 0,
            'owner_game_slots': row['game_slots'],
            'sgf_and_fk_and_rank_fields_captured': True,
        },
    }
    assert new['canonical_name'] == '高若环' and row['game_slots'] == 25
    old_scope[696] = new
    ordered = [old_scope[source['prod_player_id']] for source in packet['players']]
    assert len(ordered) == len({x['owner']['id'] for x in ordered}) == 20
    output = {
        'kind': 'post591_final20_unsigned_pending_input',
        'environment': env,
        'status': 'pending_root_source_identity_rule_review',
        'source_packet_file': packet_path.name,
        'source_packet_file_sha256': sha(packet_path),
        'source_registry_proposal_file': registry_path.name,
        'source_registry_proposal_canonical_sha256': registry_sha256(registry),
        'current591_exact19_capture_file': old['capture_file'],
        'current591_exact19_capture_file_sha256': old['capture_file_sha256'],
        'current591_replacement696_capture_file': cap_path.name,
        'current591_replacement696_capture_file_sha256': sha(cap_path),
        'preceding_batch_id': 591,
        'requires_fresh_global_inventory_and_approved_snapshot': True,
        'pending': ordered,
    }
    raw = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    outpath = D / f'{env}-post591-final20-unsigned-pending-input.json.gz'
    outpath.write_bytes(gzip.compress(raw, mtime=0))
    result[env] = {'path': outpath.name, 'sha256': sha(outpath),
                   'owners': len(ordered),
                   'game_slots': sum(x['linked_album_scope_ref']['owner_game_slots'] for x in ordered)}
(D / 'final20-unsigned-pending-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
