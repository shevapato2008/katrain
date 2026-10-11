"""Produce unsigned native pending candidates; native approval awaits root review.

The older post-590 inventory is used only for provisional owner-presence checks.
The final importer requires a fresh root-supplied global inventory/snapshot.
"""
import datetime
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_candidates import _inventory_values, _validate_candidate, canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256

D = Path(__file__).parent
FROZEN = D.parent / 'kifu-next20-2026-10-09'
REGISTRY = json.loads((D / 'source-registry-proposed-pending.json').read_text())
PACKET = json.loads((D / 'source20-post591-final-pending.json').read_text())
result = {}


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


for env in ('PROD', 'TEST'):
    pending = read(D / f'{env}-post591-final20-unsigned-pending-input.json.gz')
    research = (read(D / f'{env}-post591-final20-pending-conventional18.json.gz') +
                read(D / f'{env}-post591-final20-pending-positive-ko2.json.gz'))
    by_key = {(row['owner']['id'], row['lang']): row for row in research}
    assert len(by_key) == 20
    oldcapture = read(D / f'{env}-current591-exact20-readonly.json.gz')
    oldrows = {row['id']: row for row in oldcapture['rows']}
    replacement = read(D / f'{env}-replacement696-current591-readonly.json.gz')
    newrow = replacement['rows'][0]
    frozen = read(FROZEN / f'{env}-mixed20-fresh-post590-pages.json.gz')
    inventory_values = _inventory_values(frozen['inventory'])
    candidates, owners = [], []
    for entry in pending['pending']:
        owner = entry['owner']
        pid = owner['id']
        row = newrow if entry['prod_player_id'] == 696 else oldrows[pid]
        target = row['target_name_preimage']
        assert target == entry['target_name_preimage_13_fields']
        cap_path = D / (f'{env}-replacement696-current591-readonly.json.gz'
                        if entry['prod_player_id'] == 696 else f'{env}-current591-exact20-readonly.json.gz')
        captured = replacement if entry['prod_player_id'] == 696 else oldcapture
        research_record = by_key[(pid, entry['target_language'])]
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        candidate = {
            'owner': owner, 'lang': entry['target_language'],
            'display_name': entry['proposed_display_name'],
            'decision_kind': entry['pending_decision_kind'],
            'generation_rule_version': ('nikl-ja-ko-personal-name-v1'
                                        if entry['pending_decision_kind'] == 'generated' else 'none'),
            'name_preimage_sha256': registry_sha256(target) if target is not None else None,
            'preimage_binding': {
                'actor_id': research_record['producer_id'],
                'actor_model': research_record['producer_model'],
                'bound_at': now,
                'capture_sha256': hashlib.sha256(cap_path.read_bytes()).hexdigest(),
                'captured_at': captured['captured_at'],
                'name_preimage_sha256': registry_sha256(target) if target is not None else None,
                **({'target_name_preimage': target} if target is not None else {}),
            },
            'research_sha256': canonical_sha256(research_record),
            'producer_id': research_record['producer_id'],
            'producer_model': research_record['producer_model'],
            'produced_at': now,
            'review_status': 'pending',
        }
        _validate_candidate(candidate, research_record, REGISTRY, inventory_values)
        candidates.append(candidate)
        owners.append({'owner': owner, 'preimage': row['owner_preimage']})
    assert len(candidates) == len(owners) == 20
    assert {(x['prod_player_id'], x['proposed_name']) for x in PACKET['players']} == {
        (entry['prod_player_id'], entry['proposed_display_name']) for entry in pending['pending']}
    output = {'kind': 'post591_final20_native_pending_unsigned_draft',
              'environment': env,
              'status': 'pending_root_review_and_fresh_global_inventory',
              'source_packet': 'source20-post591-final-pending.json',
              'registry_version': REGISTRY['version'],
              'registry_sha256': registry_sha256(REGISTRY),
              'provisional_inventory_file': str(FROZEN / f'{env}-mixed20-fresh-post590-pages.json.gz'),
              'provisional_inventory_sha256': frozen['inventory']['sha256'],
              'not_a_fresh_global_inventory_claim': True,
              'owners': owners, 'candidates': candidates, 'research': research,
              'members': [{'owner': row['owner'], 'lang': row['lang']} for row in candidates],
              'target_count': 20}
    raw = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path = D / f'{env}-post591-final20-native-pending-unsigned-draft.json.gz'
    path.write_bytes(gzip.compress(raw, mtime=0))
    result[env] = {'path': path.name,
                   'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'candidates': len(candidates), 'native_pending_validated': True}
(D / 'final20-native-pending-candidate-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
