"""Summarize the already captured, bounded current-591 read-only snapshots.

No database or network access. This keeps the exact captured source packet intact.
"""
import gzip
import hashlib
import json
from pathlib import Path

D = Path(__file__).parent
IDS = (3771, 6642, 6635, 4568)
environments = {}
for env in ('PROD', 'TEST'):
    path = D / f'{env}-current591-exact20-readonly.json.gz'
    source = json.loads(gzip.decompress(path.read_bytes()))
    rows = {row['prod_player_id']: row for row in source['rows']}
    results = []
    for prod_id in IDS:
        row = rows[prod_id]
        name = row['target_name_preimage']
        evidence = row['target_evidence_preimage']
        research = evidence['research_payload']['research']
        assert row['target_lang'] == 'ko' and 'ko' not in row['qualified_languages']
        assert name['status'] == 'verified' and name['decision_kind'] == 'generated'
        assert research['scope_status'] == 'not_found_in_scope'
        assert 'positive_generation' not in research
        assert 'normative_ja_ko' not in evidence['research_payload']
        assert {check['status'] for check in research['source_checks']} == {'not_found'}
        results.append({
            'prod_player_id': prod_id,
            'player_id': row['id'],
            'canonical_name': row['owner_preimage']['canonical_name'],
            'target_name_id': name['id'],
            'target_display_name': name['display_name'],
            'target_status': name['status'],
            'target_decision_kind': name['decision_kind'],
            'target_evidence_id': evidence['id'],
            'target_evidence_revision': evidence['revision'],
            'target_name_full_13_field_preimage': name,
            'target_evidence_full_preimage': evidence,
            'qualified_languages': row['qualified_languages'],
            'positive_proof_gap': 'Retained generated research has no positive_generation and persisted evidence has no normative_ja_ko batch proof; native _qualified_name_rows excluded ko.',
            'new_source_only_proposal_ref': 'source20-v2.json',
        })
    environments[env] = {
        'capture_file': path.name,
        'capture_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'captured_at': source['captured_at'],
        'image_id': source['image_id'],
        'batch591_id': source['batch591']['id'],
        'four': results,
    }
out = {
    'kind': 'current591_four_positive_proof_gap_readonly',
    'source_packet_sha256': source['source_packet_sha256'],
    'environments': environments,
    'decision': 'Keep all four in next 20 as proof repair; verified display alone does not pass strict language qualification.',
    'limitation': 'This report performs no database operation, unsigned assembly, signing, approval, or publication.',
}
(D / 'current591-four-positive-proof-gap.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print('four strict-proof gaps confirmed in PROD and TEST')
