"""Append 696's two actual Korean Go sources to 17 validated pending records."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record

D = Path(__file__).parent
REGISTRY = json.loads((D / 'source-registry-proposed-pending.json').read_text())
SOURCES = json.loads((D / '696-actual-korean-sources.json').read_text())
SOURCE_IDS = {'696-kba-opponent': 'korea-baduk', '696-cyberoro-news': 'cyberoro'}
result = {}


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


for env in ('PROD', 'TEST'):
    pending = read(D / f'{env}-post591-final20-unsigned-pending-input.json.gz')
    entry = next(row for row in pending['pending'] if row['prod_player_id'] == 696)
    assert entry['original_name'] == '高若环' and entry['proposed_display_name'] == '가오뤄환'
    check = []
    for source in SOURCES:
        raw = (D / source['body_file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source['body_sha256']
        assert '가오뤄환' in source['body_excerpt']
        check.append({'owner': entry['owner'], 'source_id': SOURCE_IDS[source['id']],
                      'query': '가오뤄환', 'url': source['url'],
                      'fetched_at': source['fetched_at'], 'http_status': source['http_status'],
                      'status': 'found', 'candidate_name': '가오뤄환',
                      'body_sha256': source['body_sha256'], 'body_excerpt': source['body_excerpt'],
                      'language_basis': 'reviewed_text', 'observed_lang': 'ko',
                      'identity_basis': ('Korea Baduk Association official opponent row in professional women Go tournament.'
                                         if source['id'] == '696-kba-opponent' else
                                         'Cyberoro specialist news directly identifies Chinese women Go first-dan player and provides photo caption.')})
    record = {'owner': entry['owner'], 'lang': 'ko', 'source_lang': 'zh-Hans',
              'registry_version': REGISTRY['version'], 'registry_sha256': registry_sha256(REGISTRY),
              'review_status': 'pending', 'producer_id': '/root/next_player_sources_parallel',
              'producer_model': 'gpt-6; exact runtime variant unavailable',
              'produced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope_status': 'found', 'candidate_name': '가오뤄환',
              'original_name': '高若环', 'original_language': 'zh-Hans',
              'original_language_basis_url': entry['original_source_anchor']['url'],
              'source_checks': check,
              'source_capture_provenance': SOURCES,
              'owner_binding_note': entry['identity_note'],
              'source_review_note': entry['source_quality']}
    validate_research_record(record, REGISTRY)
    old = read(D / f'{env}-pending-conventional17-research.json.gz')
    assert len(old) == 17 and 696 not in {x['owner']['id'] for x in old}
    complete = old + [record]
    assert len(complete) == 18
    raw = json.dumps(complete, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path = D / f'{env}-post591-final20-pending-conventional18.json.gz'
    path.write_bytes(gzip.compress(raw, mtime=0))
    result[env] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'validated_pending_research_count': 18}
(D / 'final20-pending-conventional18-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
