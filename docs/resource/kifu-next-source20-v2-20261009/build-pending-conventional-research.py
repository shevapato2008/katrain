"""Build 17 truthful pending conventional records from retained real pages.

The remaining 3 JA-to-KO candidates require separate positive NIKL research.
This creates no approval, bundle or database change.
"""
import datetime
import gzip
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record

D = Path(__file__).parent
ROOT = D.parents[2]
REGISTRY = json.loads((D / 'source-registry-proposed-pending.json').read_text())
REGISTRY_SHA = registry_sha256(REGISTRY)
PRODUCER = '/root/next_player_sources_parallel'
MODEL = 'gpt-6; exact runtime variant unavailable'
FULL = {3771: '3771-namu-full.json', 6642: '6642-source-full.json',
        4340: '4340-source-full.json', 4041: '4041-source-full.json',
        5094: '5094-source-full.json', 3844: '3844-source-full.json'}


def read(path):
    with gzip.open(path, 'rt') if path.suffix == '.gz' else path.open() as stream:
        return json.load(stream)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def date_of(path):
    return datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat()


def excerpt(path, needle):
    rendered = BeautifulSoup(path.read_bytes(), 'html.parser').get_text(' ', strip=True)
    index = rendered.find(needle)
    assert index >= 0, (path, needle)
    return rendered[max(0, index - 45):index + max(150, len(needle) + 80)]


def external_anchor(entry):
    anchor = entry['original_source_anchor']
    assert entry['original_name'] in anchor['body_excerpt']
    return {'source_id': anchor['source_id'], 'url': anchor['url'],
            'fetched_at': anchor['fetched_at'], 'http_status': anchor['http_status'],
            'body_sha256': anchor['body_sha256'], 'body_excerpt': anchor['body_excerpt'],
            'original_name': entry['original_name'],
            'identity_basis': 'Previously approved original-language Go name for this exact owner; its full evidence preimage is retained in the bounded current-591 capture.'}


def target_check(entry):
    prod_id = entry['prod_player_id']
    proposed = entry['proposed_display_name']
    owner = entry['owner']
    source = entry['actual_target_sources']
    provenance = {}
    if prod_id in FULL:
        path = D / FULL[prod_id]
        captured = read(path)
        assert captured['metadata']['statusCode'] == 200
        source_url = captured['metadata']['sourceURL']
        lines = [line for line in captured['markdown'].splitlines() if proposed in line]
        assert lines, (prod_id, proposed)
        passage = next((line for line in lines if '李钢' in line), lines[0]) if prod_id == 5094 else lines[0]
        check = {'owner': owner, 'source_id': ('next20-namu-community-encyclopedia-ko'
                                            if prod_id in (3771, 6642, 4340, 4041)
                                            else 'wikipedia-ko' if prod_id == 5094 else 'wikipedia-zh'),
                 'query': proposed, 'url': source_url, 'fetched_at': date_of(path),
                 'http_status': 200, 'status': 'found', 'candidate_name': proposed,
                 'body_sha256': sha(captured['rawHtml'].encode()),
                 'body_excerpt': passage, 'language_basis': 'reviewed_text',
                 'observed_lang': 'ko' if prod_id != 3844 else 'zh-Hant',
                 'identity_basis': entry['identity_note']}
        title = captured['metadata']['title']
        article = {'title': title, 'passage': passage, 'passage_sha256': sha(passage.encode()),
                   'subject_identity': entry['identity_note']}
        if prod_id in (5094, 3844):
            revisions = re.findall(r'wgRevisionId[^\d]{0,20}(\d+)', captured['rawHtml'])
            assert revisions
            article['revision_id'] = revisions[0]
        else:
            article['edition'] = 'live page snapshot captured ' + date_of(path)
        check['article_evidence'] = article
        if prod_id == 5094:
            other = read(D / '5094-goratings-cn-capture.json')
            check['identity_corroboration'] = {'source_id': 'ret100-goratings-zh',
                'url': other['url'], 'fetched_at': other['fetched_at'],
                'http_status': other['http_status'], 'body_sha256': other['body_sha256'],
                'body_excerpt': other['body_excerpt'], 'original_name': entry['original_name'],
                'identity_basis': 'Independent Chinese Go player profile gives 李钢 and 1954 birth date, matching the Korean disambiguation line.'}
        else:
            check['identity_corroboration'] = external_anchor(entry)
        provenance = {'content_file': FULL[prod_id], 'content_sha256': sha(path.read_bytes()),
                      'transport': 'Firecrawl returned rawHtml, markdown and metadata.statusCode=200; hash is of returned rawHtml text, not direct requests body',
                      'article_role': 'disambiguation usage, individual red link' if prod_id == 5094 else 'Go event table'}
        if prod_id == 3844:
            provenance['published_variant'] = '亞歷山大·迪納斯塔因'
            provenance['published_variant_table_rows'] = 2
    elif prod_id == 5351:
        pairgo = source[0]
        raw_path = ROOT / pairgo['body_path']
        check = {'owner': owner, 'source_id': 'next20-pairgo-organizer-en',
                 'query': proposed, 'url': pairgo['url'],
                 'fetched_at': pairgo['fetched_at'], 'http_status': 200,
                 'status': 'found', 'candidate_name': proposed,
                 'body_sha256': pairgo['body_sha256'], 'body_excerpt': excerpt(raw_path, proposed),
                 'language_basis': 'reviewed_text', 'observed_lang': 'en',
                 'identity_basis': entry['identity_note']}
        provenance = {'organizer_GET': pairgo, 'independent_Hanzi_Latin_pair_GET': source[1]}
    else:
        assert len(source) == 3
        index, profile, cyberoro = [s['capture'] for s in source]
        assert profile['method'] == 'POST' and cyberoro['method'] == 'GET'
        assert profile['prpl_code'] == cyberoro['prpl_code']
        raw_path = ROOT / cyberoro['body_path']
        check = {'owner': owner, 'source_id': 'cyberoro',
                 'query': proposed, 'url': cyberoro['url'],
                 'fetched_at': cyberoro['fetched_at'], 'http_status': 200,
                 'status': 'found', 'candidate_name': proposed,
                 'body_sha256': cyberoro['body_sha256'], 'body_excerpt': excerpt(raw_path, proposed),
                 'language_basis': 'reviewed_text', 'observed_lang': 'ko',
                 'identity_basis': entry['identity_note']}
        provenance = {'publisher_index_GET': index,
                      'publisher_profile_actual_POST': profile,
                      'same_data_public_GET': cyberoro,
                      'independent_identity_corroboration_claimed': False}
    assert proposed in check['body_excerpt']
    return check, provenance


result = {}
for env in ('PROD', 'TEST'):
    pending = read(D / f'{env}-post591-unsigned-pending-input.json.gz')
    records = []
    for entry in pending['pending']:
        if entry['pending_decision_kind'] != 'conventional':
            continue
        check, provenance = target_check(entry)
        original = entry['original_source_anchor']
        source_lang = entry['original_source_language']
        record = {'owner': entry['owner'], 'lang': entry['target_language'],
                  'source_lang': REGISTRY['language_tags'][source_lang],
                  'registry_version': REGISTRY['version'], 'registry_sha256': REGISTRY_SHA,
                  'review_status': 'pending', 'producer_id': PRODUCER, 'producer_model': MODEL,
                  'produced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'scope_status': 'found', 'candidate_name': entry['proposed_display_name'],
                  'original_name': entry['original_name'],
                  'original_language': REGISTRY['language_tags'][source_lang],
                  'original_language_basis_url': original['url'],
                  'source_checks': [check],
                  'source_capture_provenance': provenance,
                  'source_review_note': entry['source_quality'],
                  'owner_binding_note': entry['identity_note']}
        validate_research_record(record, REGISTRY)
        records.append(record)
    assert len(records) == 17
    raw = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path = D / f'{env}-pending-conventional17-research.json.gz'
    path.write_bytes(gzip.compress(raw, mtime=0))
    result[env] = {'path': path.name, 'sha256': sha(path.read_bytes()), 'records': len(records)}
(D / 'pending-conventional17-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
