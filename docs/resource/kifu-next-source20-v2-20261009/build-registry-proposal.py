"""Create an unsigned, honest extension of the captured current-591 registry."""
import gzip
import hashlib
import json
from pathlib import Path

D = Path(__file__).parent
source = json.loads(gzip.decompress((D / 'PROD-current591-exact20-readonly.json.gz').read_bytes()))
base = source['source_registry']['registry']
entries = [
    {
        'id': 'next20-namu-community-encyclopedia-ko',
        'home_url': 'https://namu.wiki/',
        'language': 'ko',
        'tier': 'encyclopedia',
        'notes': 'Community edited encyclopedia pages with Korean Go tournament brackets; not an official Go federation. Exact article passage, captured edition, and separate same-person Japanese identity source required per candidate.',
    },
    {
        'id': 'next20-pairgo-organizer-en',
        'home_url': 'https://www.pairgo.or.jp/',
        'language': 'en',
        'tier': 'official',
        'notes': 'Actual English roster published by the World Pair Go Championship organizer; official only for its own event.',
    },
    {
        'id': 'next20-jstart-korean-reference',
        'home_url': 'https://jstart.co.kr/',
        'language': 'ko',
        'tier': 'reference',
        'notes': 'Korean Japan-study magazine article prints 진 하쿠쇼(陳柏劭); publication is not a Go federation or specialist Go publisher and does not by itself pass the conventional-name tier gate.',
    },
]
assert len({x['id'] for x in base['sources'] + entries}) == len(base['sources']) + 3
proposal = {**base, 'version': '2026-10-09-next20-source-proposal-pending-v1',
            'description': 'Unsigned proposal for source-only next20 review; no source type is promoted beyond its publisher role.',
            'sources': [*base['sources'], *entries]}
assert proposal['language_tags'] == base['language_tags']
assert proposal['language_scopes'] == base['language_scopes']
assert proposal['sources'][:-3] == base['sources']
raw = json.dumps(proposal, ensure_ascii=False, indent=2) + '\n'
(D / 'source-registry-proposed-pending.json').write_text(raw)
(D / 'source-registry-proposal-summary.json').write_text(json.dumps({
    'status': 'pending_root_registry_review',
    'base_version': base['version'],
    'base_canonical_sha256': source['source_registry']['sha256'],
    'new_entries': entries,
    'proposal_file_sha256': hashlib.sha256(raw.encode()).hexdigest(),
    'conventional_gate_warning': 'Jstart tier reference is retained as corroborating usage, not a conventional final source; owner 339 should use separately sourced positive Japanese-to-Korean generation if no qualifying Korean Go publication is found.',
}, ensure_ascii=False, indent=2) + '\n')
print('unsigned registry extension: 3 entries, old sources/scopes unchanged')
