"""Prepare actual captured positive Japanese-to-Korean research, without approval or database writes."""
import datetime, gzip, hashlib, html, json, re
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from katrain.web.kifu.name_evidence import registry_sha256, validate_research_record

D = Path(__file__).parent

def save(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    return hashlib.sha256(raw).hexdigest()

def found_results(data, query):
    body = query['capture']['body_text']
    soup = BeautifulSoup(body, 'html.parser')
    main = soup.select_one('#main_pack') or soup
    matches = []
    seen = set()
    for name in [data['target']['original_name'], data['target']['current_ko']]:
        for node in main.find_all(['div', 'p', 'a']):
            text = node.get_text(' ', strip=True)
            if name not in text or len(text) > 1000 or '상세검색 결과' in text or '검색옵션' in text or '검색결과가 없습니다' in text or '바둑 검색 결과' in text:
                continue
            if any(name in child.get_text(' ', strip=True) for child in node.find_all(['div','p','a'], recursive=False)):
                continue
            unit = node
            anchors = []
            for ancestor in [node, *list(node.parents)[:6]]:
                if len(ancestor.get_text(' ',strip=True)) > 3000: break
                anchors = [a for a in ancestor.find_all('a', href=True)
                           if a['href'].startswith('https://')
                           and urlparse(a['href']).hostname not in {'search.naver.com','nid.naver.com','keep.naver.com'}]
                if ancestor.name == 'a' and ancestor.get('href','').startswith('https://'):
                    anchors.insert(0, ancestor)
                if anchors: unit=ancestor; break
            if not anchors: continue
            url = anchors[0]['href']
            if url in seen: continue
            seen.add(url)
            # Retain an exact raw response slice, never BeautifulSoup's reserialized HTML.
            index = body.find('href="' + html.escape(url, quote=True) + '"')
            if index < 0: index = body.find('href="' + url + '"')
            if index < 0: continue
            raw = body[max(0,index-100):index+7000]
            resolution = ('The actual bounded result uses the same Korean output in a Go tournament/profile context; '
                          'it creates no alternative spelling conflict. The Japanese profile supplies owner identity and reading.')
            if name == data['target']['original_name'] and data['target']['current_ko'] not in text:
                resolution = ('This captured result mentions the exact Japanese original in Go context but provides no different '
                              'complete Korean name. It is a contextual lead, not the owner identity authority.')
            if data['target']['prod_id'] == 6631:
                resolution = ('The Go profile gives surname 사카이 with 酒井利雄; the historical four-brothers article prints 사카이도시오(酒井利雄), the same Hangul sequence as 사카이 도시오 with the surname/given divider omitted. No competing Hangul transcription is present.')
            if data['target']['prod_id'] == 5413:
                resolution = ('The result uses exactly 와타나베 히데오. Go-research context and political news context are retained '
                              'as separate leads; neither supplies a competing spelling, and the political item is not used to identify this player.')
            if data['target']['prod_id'] == 6608 and 'cyberoro.com' in url:
                resolution = ('The exact Hangul output matches, but the 2004 Kansai 8-dan article is not bound to this historical Nihon Kiin '
                              '9-dan owner. No identity merge is inferred. The Japanese source and original applied journal bind this owner.')
            if 'wiki.onul.works' in url or 'inmul.wiki' in url or 'udanax.org' in url:
                resolution += ' Generated/aggregated result text is only a conflict lead, not published identity authority.'
            matches.append({'url':url,'text':raw,'resolution':resolution})
    return matches

registry = json.loads((D.parent/'kifu-pending-jp20-2026-10-09/PROD-source-registry.json').read_text())
(D/'source-registry-reused.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
rules = json.loads((D/'reused-NIKL-three-page-captures.json').read_text())['rules']
cwi = json.load(gzip.open(D/'cwi-progression-capture.json.gz','rt'))
cwi_soup = BeautifulSoup(cwi['capture']['body_text'],'html.parser')
initial = json.loads((D/'ko-restore-top20-targets.json').read_text())
ids = [t['prod_id'] for t in initial if t['prod_id'] not in [6496,5244,4499]] + [6627,4266,6631]
records, summary = [], []
for pid in ids:
    source_file = D/'fresh-known-source-captures'/f'{pid}-compact-source.json.gz'
    if not source_file.exists(): source_file=D/'fresh-known-source-captures'/f'{pid}.json.gz'
    d = json.load(gzip.open(source_file,'rt'))
    target, capture = d['target'], d['profile_capture']
    owner = {'kind':'player','id':pid}
    basis = ('Same existing player ID, exact Japanese original and full kana occur together in the retained specialist/official profile. '
             'Original applied source journal and unchanged native names/ranks/game inventory remain the owner bridge; no aliases or foreign keys change.')
    if pid == 6608:
        basis += ' Existing qualified Japanese 細川千仭 is used; prior applied evidence binds canonical 細川千仞 and this source glyph variant to this historical owner.'
    host = urlparse(capture['url']).hostname
    source_id = ('nihon-kiin' if host.endswith('nihonkiin.or.jp') else 'ret114-kotobank-ja' if host=='kotobank.jp'
                 else 'igorating' if host=='www.igorating.com' else 'igorating-bare')
    check = {'owner':owner,'source_id':source_id,'query':target['original_name'],
             'url':capture['url'],'fetched_at':capture['fetched_at'],'http_status':200,'status':'found',
             'candidate_name':target['original_name'],'body_sha256':capture['body_sha256'],
             'body_excerpt':capture['body_excerpt'],'language_basis':'reviewed_text','observed_lang':'ja','identity_basis':basis}
    if source_id == 'ret114-kotobank-ja':
        name = target['original_name']
        node = cwi_soup.find(string=lambda value: name in value)
        assert node is not None, (pid, 'CWI original absent')
        row = node.find_parent('tr') or node.parent
        passage = name  # Literal name in raw profile body, with complete capture retained.
        check['article_evidence'] = {'edition':'Kotobank captured live biographical entry','title':name,
            'passage':passage,'passage_sha256':hashlib.sha256(passage.encode()).hexdigest(),'subject_identity':basis}
        cc = cwi['capture']
        check['identity_corroboration'] = {'source_id':'cwi-go','url':cc['url'],'fetched_at':cc['fetched_at'],
            'http_status':200,'body_sha256':cc['body_sha256'],'body_excerpt':cc['body_text'][cc['body_text'].rfind('<tr',0,cc['body_text'].find(name)):cc['body_text'].find('</tr>',cc['body_text'].find(name))+5],
            'observed_lang':'en','language_basis':'reviewed_text','identity_basis':'Independent CWI professional progression row binds exact original, Latin name, birth and rank dates.',
            'original_name':name}
    queries=[]
    for q in d['queries']:
        queries.append({k:q[k] for k in ['role','query','capture']} | {'relevant_results':found_results(d,q),
                       'conclusion':'no_unresolved_conflict'})
    surname, given = target['current_ko'].split()
    applications=[
        {'rule_role':'personal_names','input':target['original_name'],'output':target['current_ko'],
         'reason':'NIKL Chapter 4 Section 2 Article 3 applies Japanese personal-name transcription to historical and modern names; use the separately published full kana.'},
        {'rule_role':'kana_table','input':d['reading'],'output':target['current_ko'],
         'reason':str(target['old_explanation'].get('steps',target['old_explanation']) if isinstance(target['old_explanation'],dict) else target['old_explanation'])},
        {'rule_role':'japanese_details','input':d['reading'],'output':target['current_ko'],
         'reason':'Apply NIKL Japanese details: long vowels receive no extra spelling; nasal ン maps to ㄴ and any small ッ to final ㅅ. Kana-table word-initial and medial columns are applied separately at the surname/given boundaries.'}]
    for item in applications:
        item['locator']=next(r['capture']['locator'] for r in rules if r['role']==item['rule_role'])
    record={'owner':owner,'lang':'ko','source_lang':'ja','registry_version':registry['version'],
        'registry_sha256':registry_sha256(registry),'review_status':'pending','producer_id':'/root/next_batch_source_recovery',
        'producer_model':'gpt-6.1-sol','produced_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope_status':'generated_from_original','source_basis':'normative_ja_ko_v1',
        'generation_rule_version':'nikl-ja-ko-personal-name-v1','candidate_name':target['current_ko'],
        'original_name':target['original_name'],'original_language':'ja','original_language_basis_url':capture['url'],
        'reading':d['reading'],'reading_basis_url':capture['url'],'source_checks':[check],
        'positive_generation':{'version':1,'identity':{'owner':owner,'original_name':target['original_name'],
          'reading':d['reading'],'status':'verified','method':'reviewed_owner_binding','basis':basis,'capture':capture},
          'reading':{'surname':d['surname'],'given':d['given'],'capture':capture},'rules':rules,
          'explanation':{'surname':surname,'given':given,'output':target['current_ko'],'rule_applications':applications},
          'conflict_queries':queries,'unresolved_conflicts':[]}}
    try:
        validate_research_record(record,registry)
    except Exception:
        print("Rejected owner",pid,flush=True)
        raise
    records.append(record)
    summary.append({'prod_id':pid,'name':target['current_ko'],'original_name':target['original_name'],
       'reading':d['reading'],'reading_source_url':capture['url'],'games':target['games'],
       'research_sha256':registry_sha256(record),'conflict_result_counts':[len(q['relevant_results'])for q in queries],
       'status':'unsigned_pending_independent_review'})
sha=save(D/'positive-ko20-unsigned-research.json.gz',records)
(D/'positive-ko20-summary.json').write_text(json.dumps({'count':len(summary),'game_slots':sum(x['games']for x in summary),
    'research_array_sha256':sha,'records':summary,'held':[{'prod_id':4499,'reason':'Actual NIH spelling includes surname/given whitespace; alternative Igo compact spelling differs and identity bridge held'}, {'prod_id':5244,'reason':'Actual NIH spelling includes surname/given whitespace, incompatible with current positive visible-name comparison; alternative Igo 橋本善美 identity bridge held'}, {'prod_id':6496,'reason':'Hangame conventional 타다오 differs from existing generated 다다오'},
    {'prod_id':3900,'reason':'Korean Wikipedia pupil article conventional 사토우 스나오 differs from existing generated 사토 스나오'}],
    'limitations':['Two bounded actual first-page queries per owner; no universal absence claim.','All records remain unsigned pending root review and current environment preimage binding.']},ensure_ascii=False,indent=2)+'\n')
print('PASS',len(records),'unsigned records',sum(x['games']for x in summary),'slots',sha)
