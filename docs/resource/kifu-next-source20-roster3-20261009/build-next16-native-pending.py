"""Build unsigned native pending records from fresh scoped captures and saved source bodies.

Four community-only Korean names remain source-level holds under the current
conventional gate. Root can add separately sourced replacement rows later.
No approval, SQL, signature, Git operation, or full approved-name scan occurs.
"""
import datetime
import gzip
import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
from katrain.web.kifu.name_candidates import _inventory_values, _validate_candidate, canonical_sha256
from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record

D = Path(__file__).resolve().parent
V2 = D.parent / 'kifu-next-source20-v2-20261009'
HOLD = {4071, 6329, 5495, 4331}
PRODUCER = '/root/next_player_sources_parallel'
MODEL = 'gpt-6; exact runtime variant unavailable'


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_body(source):
    path = D / source['body_file']
    raw = gzip.open(path, 'rb').read() if path.suffix == '.gz' else path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == source['body_sha256']
    assert len(raw) == source['body_bytes'] and source.get('http_status', source.get('status')) == 200
    return raw


def excerpt(source, needle, *, width=190):
    raw = raw_body(source)
    visible = BeautifulSoup(raw, 'html.parser').get_text(' ', strip=True)
    pos = visible.find(needle)
    if pos < 0:
        visible = raw.decode('utf-8', errors='replace')
        pos = visible.find(needle)
    assert pos >= 0, (source['url'], needle)
    return visible[max(0, pos - 50):pos + width]


def actual_time(source):
    return source.get('fetched_at_utc', source.get('fetched_at'))


def target_source(record):
    pid = record['prod_player_id']
    if record['missing_language'] == 'ko':
        source = next(s for s in record['sources'] if s['url'].startswith('https://www.baduk.or.kr/'))
        return source, 'korea-baduk', 'ko'
    if pid == 5034:
        return record['sources'][0], 'ret157-kifudepot-ja', 'ja'
    if pid == 5036:
        source = next(s for s in record['sources'] if s['url'] == 'https://db.u-go.net/2082/')
        return source, 'ret97-ugo-en', 'en'
    if pid == 5296:
        return record['sources'][0], 'ret110-taiwango-tw', 'zh-Hant'
    raise ValueError(pid)


def register_daum(registry):
    source_id = 'roster3-daum-community-ko-reference'
    assert source_id not in {source['id'] for source in registry['sources']}
    registry = json.loads(json.dumps(registry))
    registry['version'] = '2026-10-09-roster3-reference-v1'  # existing VARCHAR(64) boundary
    registry['sources'].append({
        'id': source_id,
        'home_url': 'https://m.cafe.daum.net/clubA7bodook/',
        'language': 'ko',
        'tier': 'reference',
        'notes': '2012 Go community bilingual player roster, named author; no association or original-publisher endorsement established. Korean/Hanzi same-line identity bridge, not a conventional-name qualifying tier.',
    })
    return registry, source_id


def original_anchor(row, record):
    name = record['existing_qualified_names']['cn']
    old = next(n for n in row['all_name_preimages_13_fields']
               if n['lang'] == 'cn' and n['display_name'] == name)
    evidence = next(e for e in row['all_owner_evidence_preimages'] if e['id'] == old['evidence_id'])
    checks = evidence['research_payload']['research']['source_checks']
    found = [check for check in checks if check['status'] == 'found' and check['candidate_name'] == name]
    assert found, (record['prod_player_id'], name)
    return found[0]


def build(env):
    proposal = read(D / 'next20-source-only-firstpass-proposal.json')
    request = read(D / 'next16-current-scoped-request.json')
    capture_file = D / f'{env}-next16-current-scoped-readonly.json.gz'
    capture = read(capture_file)
    assert capture['request_sha256'] == digest(D / 'next16-current-scoped-request.json')
    assert len(capture['rows']) == 16
    rows = {x['prod_player_id']: x for x in capture['rows']}
    source_rows = {x['prod_player_id']: x for x in proposal['records'] if x['prod_player_id'] not in HOLD}
    assert set(rows) == set(source_rows) == {x['prod_player_id'] for x in request['rows']}
    registry, daum_id = register_daum(capture['source_registry']['registry'])
    registry_sha = registry_sha256(registry)
    # The older immutable global inventory is only a provisional finite owner
    # membership check. Root must attach a fresh native inventory before signing.
    base = read(V2 / f'{env}-post591-global-readonly.json.gz')['inventory']
    values = _inventory_values(base)
    research, candidates, owners = [], [], []
    for record in proposal['records']:
        pid = record['prod_player_id']
        if pid in HOLD:
            continue
        row = rows[pid]
        owner = {'kind': 'player', 'id': row['id']}
        assert row['target_lang'] == record['missing_language']
        assert row['qualified_languages'] == sorted(record['existing_qualified_names'])
        original = original_anchor(row, record)
        primary, source_id, observed_lang = target_source(record)
        proposed = record['proposed_display_name']
        checks = [{
            'owner': owner, 'source_id': source_id, 'query': proposed,
            'url': primary['url'], 'fetched_at': actual_time(primary), 'http_status': 200,
            'status': 'found', 'candidate_name': proposed,
            'body_sha256': primary['body_sha256'], 'body_excerpt': excerpt(primary, proposed),
            'language_basis': 'reviewed_text', 'observed_lang': observed_lang,
            'identity_basis': record['identity_note'],
        }]
        daum = next((s for s in record['sources'] if s.get('id') == 'daum-korean-list'), None)
        if daum:
            checks.append({
                'owner': owner, 'source_id': daum_id, 'query': proposed,
                'url': daum['url'], 'fetched_at': actual_time(daum), 'http_status': 200,
                'status': 'found', 'candidate_name': proposed,
                'body_sha256': daum['body_sha256'], 'body_excerpt': excerpt(daum, proposed, width=110),
                'language_basis': 'reviewed_text', 'observed_lang': 'ko',
                'identity_basis': 'Historical bilingual Go community roster, source tier reference only; full Hanzi in the same paragraph bridges the owner’s Chinese original.',
            })
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        research_record = {
            'owner': owner, 'lang': record['missing_language'],
            'source_lang': 'zh-Hans', 'registry_version': registry['version'],
            'registry_sha256': registry_sha, 'review_status': 'pending',
            'producer_id': PRODUCER, 'producer_model': MODEL, 'produced_at': now,
            'scope_status': 'found', 'candidate_name': proposed,
            'original_name': record['existing_qualified_names']['cn'],
            'original_language': 'zh-Hans',
            'original_language_basis_url': original['url'], 'source_checks': checks,
            'source_capture_provenance': record['sources'],
            'owner_binding_note': record['identity_note'],
            'source_review_note': 'Primary target display is in a qualifying specialist or official source; Daum is reference-tier identity context only.',
        }
        validate_research_record(research_record, registry)
        target = row['target_name_preimage']
        assert target is None or len(target) == 13
        candidate = {
            'owner': owner, 'lang': record['missing_language'], 'display_name': proposed,
            'decision_kind': 'conventional', 'generation_rule_version': 'none',
            'name_preimage_sha256': registry_sha256(target) if target is not None else None,
            'preimage_binding': {
                'actor_id': PRODUCER, 'actor_model': MODEL, 'bound_at': now,
                'capture_sha256': digest(capture_file), 'captured_at': capture['captured_at'],
                'name_preimage_sha256': registry_sha256(target) if target is not None else None,
                **({'target_name_preimage': target} if target is not None else {}),
            },
            'research_sha256': canonical_sha256(research_record),
            'producer_id': PRODUCER, 'producer_model': MODEL, 'produced_at': now,
            'review_status': 'pending',
        }
        _validate_candidate(candidate, research_record, registry, values)
        research.append(research_record)
        candidates.append(candidate)
        owners.append({'owner': owner, 'preimage': row['owner_preimage']})
    assert len(candidates) == len(research) == len(owners) == 16
    output = {
        'kind': 'roster3_native_pending_unsigned_draft', 'environment': env,
        'status': 'pending_root_review_and_fresh_inventory; four_reference_only_held',
        'proposal_sha256': digest(D / 'next20-source-only-firstpass-proposal.json'),
        'scoped_capture_file': capture_file.name, 'scoped_capture_sha256': digest(capture_file),
        'registry': registry, 'registry_sha256': registry_sha,
        'provisional_inventory_file': str(V2 / f'{env}-post591-global-readonly.json.gz'),
        'provisional_inventory_sha256': base['sha256'],
        'not_a_fresh_inventory_claim': True,
        'catalog_sha256': capture['catalog_sha256'],
        'latest_batch': capture['latest_batch'],
        'source_level_hold_ids': sorted(HOLD),
        'owners': owners, 'candidates': candidates, 'research': research,
        'members': [{'owner': x['owner'], 'lang': x['lang']} for x in candidates],
    }
    path = D / f'{env}-next16-native-pending-unsigned-draft.json.gz'
    if path.exists():
        raise FileExistsError(path)
    raw = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    print(env, len(candidates), path.name, digest(path))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', choices=['PROD', 'TEST'], required=True)
    args = parser.parse_args()
    build(args.env)
