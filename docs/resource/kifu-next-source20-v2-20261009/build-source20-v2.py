"""Assemble source-only research from retained public responses and frozen read-only files."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import collections
import gzip
import json

D = Path(__file__).parent
ROOT = D.parents[2]
OLD = ROOT / 'docs/resource/kifu-next-highfreq20-source-only-2026-10-09'
FROZEN = ROOT / 'docs/resource/kifu-next20-2026-10-09'
PROD = FROZEN / 'PROD-mixed20-fresh-post590-pages.json.gz'
TEST = FROZEN / 'TEST-mixed20-fresh-post590-pages.json.gz'

def read(path):
    with gzip.open(path,'rt') if str(path).endswith('.gz') else open(path) as stream:
        return json.load(stream)

def sha(path): return sha256(path.read_bytes()).hexdigest()

def rel(path): return str(path.relative_to(ROOT))

def md_source(stem, url, snippet, scrape_id=None):
    path = D / (stem+'.md')
    assert snippet in path.read_text(), (stem,snippet)
    return {'url':url,'method':'GET via Firecrawl scrape','transport':'extracted_markdown',
            'content_file':rel(path),'content_sha256':sha(path),
            'retained_at_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
            'scrape_id':scrape_id,'direct_visible_excerpt':snippet}

p = read(PROD); t = read(TEST)
prod_names=collections.defaultdict(dict);test_names=collections.defaultdict(dict)
for capture, target in ((p,prod_names),(t,test_names)):
    for row in capture['approved_name_snapshot']:
        if row['owner']['kind']=='player' and row['lang'] in ('cn','tw','jp','ko','en'):
            target[row['owner']['id']][row['lang']]=row['display_name']
by_names=collections.defaultdict(list)
for pid,names in test_names.items():by_names[tuple(sorted(names.items()))].append(pid)
cols=p['inventory']['association_columns'];si=(cols.index('black_player_id'),cols.index('white_player_id'))
slots=collections.Counter()
for row in p['inventory']['album_associations']:
    for i in si:
        if row[i] is not None: slots[row[i]]+=1

old = {row['prod_player_id']:row for row in read(OLD/'source-only-20-research.json')['players']}
tv=read(D/'tvbaduk-captures.json')
tv_profiles={row['prod_player_id']:row for row in tv['profiles']}
cyberoro={row['prod_player_id']:row for row in read(D/'cyberoro-captures.json')}
static={row['id']:row for row in read(D/'static-captures.json')}
for capture in [tv['china_index'], tv['taiwan_index'], *tv_profiles.values(), *cyberoro.values(), *static.values()]:
    if capture.get('body_file'):
        capture['body_path'] = rel(D / capture['body_file'])
for row in static.values():
    if row['body_file']:
        assert sha(D/row['body_file'])==row['body_sha256']
for row in tv_profiles.values():assert sha(D/row['body_file'])==row['body_sha256']

JP_OLD = {
 3771:('시모히라 아키오','3771-namu','https://namu.wiki/w/%EC%A0%9C45%ED%9A%8C%20%ED%98%BC%EC%9D%B8%EB%B3%B4%EC%A0%84','01a11d27-200a-71ab-85bb-156fb5316d1d'),
 6642:('다이나카 신','6642-namu','https://namu.wiki/w/%EC%A0%9C1%ED%9A%8C%20%EC%8B%AD%EB%8B%A8%EC%A0%84(%EC%9D%BC%EB%B3%B8)','01a11d27-2015-775d-9bc9-c84ba2e88aaf'),
}
NEW_NAMU={
 4340:('안도 히나타','4340-namu','https://namu.wiki/w/%EC%A0%9C49%ED%9A%8C%20(%EC%86%8C)%EA%B8%B0%EC%84%B1%EC%A0%84','01a11d2e-8a50-7707-b27a-04744276941f'),
 4041:('마에다 료','4041-namu','https://namu.wiki/w/%EC%A0%9C50%ED%9A%8C%20%EC%B2%9C%EC%9B%90%EC%A0%84(%EC%9D%BC%EB%B3%B8)','01a11d2e-8a3f-702b-a5e0-408352bdeadd'),
}
TV={368:('자오젠난','full Hanja 趙健男 matches existing JP/TW'),
    3820:('차오스야오','partial Hanja 乔诗; third character absent; Daum line pairs 乔诗尧'),
    4634:('장자야오','full Hanja 張家尧 matches existing name variants'),
    5133:('양원카이','full Hanja 楊文铠 matches existing name variants'),
    5473:('왕보강','partial Hanja 王伯; third character absent; Daum line pairs 王伯刚'),
    5675:('친쓰웨','full Hanja 秦思玥 matches existing name'),
    5790:('판시위','full Hanja 範希鈺 matches existing JP/TW'),
    6296:('천야펑','full Hanja 陳亚峰 matches existing name variants'),
    6378:('천창칭','Hanja 陳長淸 uses variant 淸 where existing name has 清; other characters match'),
    6547:('황량위','mixed bracket 황良玉 is not full Hanja; two given-name characters match 黄良玉; Daum pairs them')}

ORDER=[3771,6642,6635,4568,5094,368,3820,4634,5133,5473,5675,5790,6296,6378,6547,5351,4340,4041,339,3844]
assert len(ORDER)==len(set(ORDER))==20
rows=[]
for pid in ORDER:
    names=prod_names[pid]
    matches=by_names[tuple(sorted(names.items()))]
    assert len(names)==4 and len(matches)==1 and len({'cn','tw','jp','ko','en'}-set(names))==1
    row={'prod_player_id':pid,'test_player_id':matches[0],'linked_slots_per_environment':slots[pid],
         'missing_language':next(iter({'cn','tw','jp','ko','en'}-set(names))),
         'existing_qualified_names':{k:names[k] for k in sorted(names)},
         'source_only':True,'no_owner_binding_or_approval':True}
    if pid in JP_OLD:
        proposal,stem,url,scrape_id=JP_OLD[pid]
        row.update(proposed_name=proposal,evidence_kind='direct_korean_go_tournament_table',
                   source_quality='Korean community Go tournament page directly prints the whole Hangul name; Japanese specialist profile gives exact kanji and complete kana.',
                   identity_note='Korean table has the full Korean reading in Go competition context; original Japanese identity and kana are retained in the earlier source-only record.',
                   sources=[md_source(stem,url,proposal,scrape_id),old[pid]['japanese_profile']],
                   legacy_research_ref=rel(OLD/'source-only-20-research.json'))
    elif pid in (6635,4568):
        prior=old[pid]
        jpid='6635' if pid==6635 else '4568'
        search=[]
        for suffix in ('jp','spell'):
            path=D/f'search-{jpid}-{suffix}.json';a=read(path)
            search.append({'query_capture':rel(path),'file_sha256':sha(path),'search_id':a['id'],
                           'returned_result_count':len(a.get('data',{}).get('web',[]))})
        row.update(proposed_name=prior['source_only_proposal'],evidence_kind='generated_korean_from_complete_japanese_kana',
                   source_quality='Actual Japanese specialist profile prints full kanji plus kana; retained NIKL rules support syllable mapping. Two limited Korean web queries were run, but this does not prove global nonpublication.',
                   identity_note='No direct same-person Korean publication found in the two recorded queries; generated spelling remains for root review.',
                   sources=[prior['japanese_profile'],prior['normative_rule_capture']],
                   limited_conflict_queries=search,legacy_research_ref=rel(OLD/'source-only-20-research.json'))
    elif pid==5094:
        row.update(proposed_name='리강',evidence_kind='direct_korean_wikipedia_disambiguation',
                   source_quality='Korean Wikipedia disambiguation body explicitly says 리강 (李钢, 1954 ~ ) is a Chinese Go player. The person link is a red link, not an existing biography.',
                   identity_note='Exact Hanzi, 1954 birth year and Go occupation disambiguate this person.',
                   sources=[md_source('5094-kowiki','https://ko.wikipedia.org/w/index.php?title=%EB%A6%AC%EA%B0%95&oldid=36505438','리강 (바둑 기사)', '01a11d27-201f-71e8-99fb-777248f0e2ee')])
    elif pid in TV:
        proposal,note=TV[pid];profile=tv_profiles[pid]
        assert profile['name_in_index']==proposal and proposal in profile['visible_profile_excerpt']
        index=tv['taiwan_index'] if pid==6378 else tv['china_index']
        url=cyberoro[pid]['url']
        row.update(proposed_name=proposal,evidence_kind='direct_korean_professional_go_player_profile',
                   source_quality='Korea Baduk Association affiliated Baduk TV index and player profile publish complete Hangul name; profile bracket Hanja quality varies and is described separately.',
                   identity_note=note+'; stable prpl_code='+profile['prpl_code']+'; profile lists '+('Taiwan' if pid==6378 else 'China')+' Go association and dan rank.',
                   sources=[{'role':'index','capture':index,'name_as_published':proposal},
                            {'role':'profile','capture':profile},
                            {'role':'same-code public GET profile; same underlying data, not independent corroboration','capture':cyberoro[pid]}],
                   review_flag='partial_hanzi_identity_review' if pid in (3820,5473,6547) else None)
    elif pid==5351:
        row.update(proposed_name='Sha Xingyu',evidence_kind='direct_english_organizer_roster',
                   source_quality='World Pair Go Association organizer roster prints Sha Xingyu, 6 dan, China, Shanghai International Studies University; a separate tournament schedule pairs Sha,Xingyu with 沙星宇.',
                   identity_note='Published Hanzi and English paired in the Sina schedule; organizer roster independently identifies same named Chinese Go player and university.',
                   sources=[static['5351-pairgo'],static['5351-sina']])
    elif pid in NEW_NAMU:
        proposal,stem,url,scrape_id=NEW_NAMU[pid]
        orig=static['4340-kansai' if pid==4340 else '4041-igo']
        row.update(proposed_name=proposal,evidence_kind='direct_korean_go_tournament_table',
                   source_quality='Korean Go competition table directly prints full Hangul name. Japanese original profile prints full kanji, kana and Go-player context.',
                   identity_note='Direct tournament spelling matches the independently published complete Japanese reading.',
                   sources=[md_source(stem,url,proposal,scrape_id),orig])
    elif pid==339:
        row.update(proposed_name='진 하쿠쇼',evidence_kind='direct_korean_news_article',
                   source_quality='Korean education publication directly writes 진 하쿠쇼(陳柏劭) and says he is a Japanese professional Go player from Taiwan.',
                   identity_note='Exact full Hanja and Go profession, with Japanese university and qualification context.',
                   sources=[static['339-jstart']])
    elif pid==3844:
        row.update(proposed_name='亞歷山大·迪那斯塔因',evidence_kind='direct_zh_hant_wikipedia_go_event_table',
                   source_quality='Traditional Chinese Wikipedia view directly prints this complete name in several Go match results. The same page also uses 迪納斯塔因 once; this is a real spelling variation, so root should choose the preferred form.',
                   identity_note='Matches Alexander Dinerchtein as the European Go participant in the event; existing CN name uses 迪那斯塔因 without the middle dot.',
                   sources=[md_source('3844-zhtw-wiki','https://zh.wikipedia.org/zh-hant/%E7%AC%AC%E5%9B%9B%E5%B1%86%E4%B8%96%E7%95%8C%E6%99%BA%E5%8A%9B%E7%B2%BE%E8%8B%B1%E8%BF%90%E5%8B%95%E6%9C%83','亞歷山大·迪那斯塔因','01a11d29-3a7f-75b8-80c5-dab097646668')],
                   review_flag='same_page_tw_spelling_variant_迪納')
    rows.append(row)

result={'packet_kind':'source_only_research','produced_at':datetime.now(timezone.utc).isoformat(),
        'basis':{'prod_frozen_capture':rel(PROD),'prod_frozen_file_sha256':sha(PROD),
                 'test_frozen_capture':rel(TEST),'test_frozen_file_sha256':sha(TEST),
                 'prod_inventory_sha256':p['inventory']['sha256'],'test_inventory_sha256':t['inventory']['sha256'],
                 'preceding_batch':590,'excluded_prepared_mixed20':read(OLD/'source-only-20-research.json')['basis']['excluded_prepared_mixed20']},
        'scope':{'distinct_players':20,'linked_slots_per_environment':sum(x['linked_slots_per_environment'] for x in rows),
                 'missing_language_counts':dict(collections.Counter(x['missing_language'] for x in rows))},
        'limitations':['Source-only: no database fresh capture, SQL, target preimage, approval/signature, Git or deployment.',
                       'Korean direct publication and same-person binding are different checks. Partial-Hanzi Baduk TV profiles are flagged for root adjudication; bracket text is never represented as a full Chinese name.',
                       'Firecrawl-scraped markdown is stored as extracted content with its file hash and time, not mislabeled as raw HTTP response. Raw TV Baduk POST bodies and exact form data are retained.',
                       'Search returns are finite observations, not global absence proof; the two generated names are labeled accordingly.',
                       'Source pages are not automatically current owner authoritative_pages; root must perform its later fresh binding.'],
        'players':rows}
(D/'source20-v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# Next 20 distinct players — source-only v2','',
       'Frozen post-590 inventory selection. 20 distinct owner pairs; no database query/write, signing, Git or deployment. Root owns current source binding and approval.','',
       '| PROD / TEST | Slots | Missing | Proposed name | Source type | Review note |','|---|---:|---|---|---|---|']
for x in rows:
    note=x.get('review_flag') or ('generated; finite conflict searches' if x['evidence_kind'].startswith('generated') else '')
    lines.append(f"| {x['prod_player_id']} / {x['test_player_id']} | {x['linked_slots_per_environment']} | {x['missing_language']} | {x['proposed_name']} | {x['evidence_kind']} | {note} |")
lines += ['', '## Source-quality boundaries','',
          'Baduk TV is a Korea Baduk Association affiliated Go broadcaster. Its player index is GET; individual profiles were actually fetched by POST to `gisa_view.asp` with retained `prpl_code` and form fields. Cyberoro GET profile URLs use the same player code and data, so they are access links, not independent identity corroboration.','',
          'For 3820, 5473 and 6547, profile bracket Hanzi are partial or mixed Hangul/Hanzi. The whole Hangul name appears in the professional profile; retained Daum pairings are identity leads, not an upgrade of the incomplete bracket to full Hanzi. The root should adjudicate those three.','',
          'For 3844, the same Traditional Chinese Wikipedia Go event page contains both 迪那斯塔因 and 迪納斯塔因. The proposed 迪那 form is directly published and matches the existing CN base; retain the variant flag.','',
          'For 6635 and 4568, the proposed Hangul is generated from full Japanese kana and retained NIKL rules. The two additional actual search responses per owner are saved, and no global absence is claimed.','',
          f"Frozen PROD SHA-256 `{sha(PROD)}`; TEST SHA-256 `{sha(TEST)}`. Detailed URLs, methods, form data, content paths, timestamps and hashes are in `source20-v2.json`.",'']
(D/'source20-v2.md').write_text('\n'.join(lines))
print('source-only',len(rows),'slots',sum(x['linked_slots_per_environment'] for x in rows))
