"""Prepare two pending positive JA-to-KO records with real kana and NIKL pages."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path

from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record

D = Path(__file__).parent
OLD = D.parent / 'kifu-next-highfreq20-source-only-2026-10-09'
RULES = json.loads((D.parent / 'kifu-next-throughput-2026-10-09/reused-NIKL-three-page-captures.json').read_text())['rules']
SEARCH = json.loads((D / 'positive-two-query-kowiki-captures.json').read_text())
REGISTRY = json.loads((D / 'source-registry-proposed-pending.json').read_text())
OLD_SOURCE = {x['prod_player_id']: x for x in json.loads((OLD / 'source-only-20-research.json').read_text())['players']}
NAME = {
    6635: {'ja_surname': 'まえたに', 'ja_given': 'しんご', 'ko_surname': '마에타니', 'ko_given': '신고',
           'reasons': 'ま→마, え→에, た→타, に→니; initial し→시, ん→ㄴ, ご→고.'},
    4568: {'ja_surname': 'かわむら', 'ja_given': 'まさみち', 'ko_surname': '가와무라', 'ko_given': '마사미치',
           'reasons': 'initial か→가, わ→와, む→무, ら→라; ま→마, さ→사, み→미, ち→치.'},
}


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def positive_capture(profile):
    path = OLD / profile['raw_body_file']
    body = path.read_bytes().decode('utf-8')
    assert sha(body) == profile['raw_body_sha256']
    return {'url': profile['url'], 'http_status': profile['http_status'],
            'fetched_at': profile['fetched_at'], 'body_text': body,
            'body_sha256': sha(body), 'body_excerpt': body,
            'locator': 'Complete retained Japanese professional Go profile HTML; name and full kana occur in visible text',
            'source_role': 'professional_go_rating_archive', 'observed_lang': 'ja'}


def conflict_capture(item):
    path = D / item['body_file']
    body = path.read_bytes().decode('utf-8')
    assert sha(body) == item['body_sha256']
    return {'url': item['url'], 'http_status': item['http_status'],
            'fetched_at': item['fetched_at'], 'body_text': body,
            'body_sha256': sha(body), 'body_excerpt': body[:min(250, len(body))],
            'locator': 'Korean Wikipedia API finite query, actual 200 JSON response; returned titles and count retained',
            'source_role': 'search_results', 'observed_lang': 'ko'}


results = {}
for env in ('PROD', 'TEST'):
    pending = read(D / f'{env}-post591-final20-unsigned-pending-input.json.gz')
    rows = {x['prod_player_id']: x for x in pending['pending']}
    records = []
    for pid in (6635, 4568):
        entry = rows[pid]
        source = OLD_SOURCE[pid]
        spelling = NAME[pid]
        original = entry['original_name']
        reading = spelling['ja_surname'] + ' ' + spelling['ja_given']
        output = spelling['ko_surname'] + ' ' + spelling['ko_given']
        assert source['japanese_reading'] == reading and entry['proposed_display_name'] == output
        capture = positive_capture(source['japanese_profile'])
        owner = entry['owner']
        identity_basis = ('Retained actual Japanese Go rating profile prints original name and complete kana; '
                          'current-591 read-only owner has matching qualified JP/EN identity, canonical name and game scope. '
                          'Old verified generated KO row remains strictly unqualified because its persisted positive batch proof is missing.')
        check = {'owner': owner, 'source_id': 'igorating', 'query': original,
                 'url': capture['url'], 'fetched_at': capture['fetched_at'], 'http_status': 200,
                 'status': 'found', 'candidate_name': original,
                 'body_sha256': capture['body_sha256'], 'body_excerpt': capture['body_excerpt'],
                 'language_basis': 'reviewed_text', 'observed_lang': 'ja',
                 'identity_basis': identity_basis}
        queries = []
        for role in ('original_go', 'candidate_go'):
            item = next(x for x in SEARCH if x['player_id'] == pid and x['role'] == role)
            queries.append({'role': role, 'query': item['query'],
                            'capture': conflict_capture(item), 'relevant_results': [],
                            'conclusion': 'no_unresolved_conflict'})
        applications = [
            {'rule_role': 'personal_names', 'input': original, 'output': output,
             'reason': 'NIKL Chapter 4 Japanese personal-name rule applies to the complete published Japanese name.'},
            {'rule_role': 'kana_table', 'input': reading, 'output': output,
             'reason': spelling['reasons'] + ' Surname and given name are separately word initial.'},
            {'rule_role': 'japanese_details', 'input': reading, 'output': output,
             'reason': 'Official NIKL Japanese details checked; no long vowel or small っ changes this output.'},
        ]
        for application in applications:
            application['locator'] = next(r['capture']['locator'] for r in RULES
                                          if r['role'] == application['rule_role'])
        record = {'owner': owner, 'lang': 'ko', 'source_lang': 'ja',
                  'registry_version': REGISTRY['version'], 'registry_sha256': registry_sha256(REGISTRY),
                  'review_status': 'pending', 'producer_id': '/root/next_player_sources_parallel',
                  'producer_model': 'gpt-6; exact runtime variant unavailable',
                  'produced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'scope_status': 'generated_from_original', 'source_basis': 'normative_ja_ko_v1',
                  'generation_rule_version': 'nikl-ja-ko-personal-name-v1',
                  'candidate_name': output, 'original_name': original,
                  'original_language': 'ja', 'original_language_basis_url': capture['url'],
                  'reading': reading, 'reading_basis_url': capture['url'],
                  'source_checks': [check],
                  'positive_generation': {'version': 1,
                      'identity': {'owner': owner, 'original_name': original, 'reading': reading,
                                   'status': 'verified', 'method': 'reviewed_owner_binding',
                                   'basis': identity_basis, 'capture': capture},
                      'reading': {'surname': spelling['ja_surname'], 'given': spelling['ja_given'],
                                  'capture': capture},
                      'rules': RULES,
                      'explanation': {'surname': spelling['ko_surname'], 'given': spelling['ko_given'],
                                      'output': output, 'rule_applications': applications},
                      'conflict_queries': queries, 'unresolved_conflicts': []},
                  'finite_query_note': 'Only the four exact recorded Wikipedia API query responses were reviewed; no global nonpublication claim.'}
        validate_research_record(record, REGISTRY)
        records.append(record)
    assert len(records) == 2
    raw = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path = D / f'{env}-post591-final20-pending-positive-ko2.json.gz'
    path.write_bytes(gzip.compress(raw, mtime=0))
    results[env] = {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'validated_pending_research_count': 2}
(D / 'final20-pending-positive-ko2-manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False))
