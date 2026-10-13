"""Independent read-only decision material builder; no database mutation code."""
import collections
import datetime
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from katrain.core.sgf_parser import SGF

BASE = ROOT / 'docs/resource'
SOURCE = BASE / 'kifu-player-exact-anchor-top20-independent-sources-astra-2026-10-04'
def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes())
def pin(path):
    return {'path': str(path.relative_to(ROOT)), 'file_sha256': sha(path)}

SNAPS = {env: load(BASE / f'kifu-player-exact-anchor-top20-{env}-post-korean-expanded-full-preimage-astra-2026-10-04.json.gz') for env in ['TEST','PROD']}
ALBUMS = {env: {r['id']: r for r in s['albums']} for env,s in SNAPS.items()}
SOURCES = {env: collections.defaultdict(list) for env in SNAPS}
for env,s in SNAPS.items():
    for r in s['album_sources']: SOURCES[env][r['album_id']].append(r)

IDENTITIES = {
 '张涛': ('Zhang Tao', 'cwa-zhangtao', 247, 246, '1991-03-23', '2004-07-24'),
 '韩升周': ('Han Seungju', 'kba-han-seungju', None, None, '1996-11-27', '2013-01-20'),
 '奥田彩': ('Okuda Aya', 'nihon-okuda', None, None, '1988-11-27', '2004'),
 '工藤纪夫': ('Kudo Norio', 'nihon-kudo', 348, 347, '1940-08-02', '1955'),
 '周鹤洋': ('Zhou Heyang', 'cwa-zhouheyang', 1048, 4193, '1976-06-18', '1988-06-25'),
 '中小野田智己': ('Nakaonoda Tomomi', 'nihon-nakaonoda', None, None, '1970-03-30', '1984'),
 '鹤田和志': ('Tsuruta Kazushi', 'nihon-tsuruta', None, None, '1995-05-14', '2010'),
 '姚智腾': ('Yao Zhiteng', 'nihon-yao', None, None, '1998-01-31', '2013'),
 '谷口彻': ('Taniguchi Toru', 'kansai-taniguchi', 157, 156, '1996-05-15', '2011-09'),
 '赵善津': ('Cho Sonjin', 'nihon-cho', 542, 541, '1970-04-18', '1984'),
 '辻笃仁': ('Tsuji Shigehito', 'kansai-tsuji', None, None, '2002-03-26', '2017-07'),
 '黄宰渊': ('Hwang Jaeyeon', 'kba-hwang-jaeyeon', 216, 215, '1995-04-08', '2011-08-20'),
 '横塚力': ('Yokotsuka Riki', 'nihon-yokotsuka', 245, 244, '1994-11-22', '2015'),
 '陈一纯': ('Chen Yichun', 'cwa-chenyichun', 20, 20, '2001-10-22', '2017-07-23'),
 '田中康湧': ('Tanaka Koyu', 'kansai-tanaka', 631, 630, '2001-06-14', '2017-08'),
 '河灿锡': ('Ha Chanseok', 'kba-ha-chanseok', 12413, 6644, '1948-12-20', '1963'),
 '久保胜昭': ('Kubo Katsuaki', 'kansai-kubo', None, None, '1958-02-07', '1972-09'),
 '李小溪05': ('Li Xiaoxi (born 2005)', 'cwa-lixiaoxi-younger', 183, 182, '2005-09-06', '2019-08-23'),
 '韩钟振': ('Han Jongjin', 'kba-han-jongjin', 167, 166, '1979-06-02', '1996'),
 '村岛谊纪': ('Murashima Yoshinori, formerly Yoshikatsu', 'wiki-murashima', 12370, 6606, '1905-03-19', '1920'),
}

# Granularity is retained: year-only or month-only promotion sources allow the
# preceding grade during the same reported interval, never a guessed exact day.
TIMELINES = {
 '工藤纪夫': [('1955',1),('1955',2),('1958',3),('1959',4),('1961',5),('1963',6),('1966',7),('1969',8),('1976',9)],
 '谷口彻': [('2011-09',1),('2014-09',2),('2017-01',3),('2019-12',4),('2021-01',5),('2025-12',6)],
 '赵善津': [('1984',1),('1984',2),('1985',3),('1986',4),('1988',5),('1989',6),('1992',7),('1994',8),('1998',9)],
 '黄宰渊': [('2011-08-20',1),('2012-07-04',2),('2014-02-04',3),('2016-05-22',4),('2020-10-19',5),('2024-04-17',6),('2026-03-31',7)],
 '横塚力': [('2015',1),('2017',2),('2018',3),('2019',7),('2026',8)],
 '田中康湧': [('2017-08',1),('2020-02',2),('2022-01',3),('2023-01',4),('2024-01',5)],
 '河灿锡': [('1963',1),('1987-01-01',8),('2003-02-08',9)],
 '韩钟振': [('1996',1),('1997',2),('1998',3),('2001-07-20',4),('2003-08-01',5),('2005-04-01',6),('2007-01-10',7),('2010-04-08',8),('2014-05-19',9)],
 '村岛谊纪': [('1920',1),('1923',2),('1925',3),('1929',5),('1943',6),('1954',7),('1966',8)],
}
for raw in ['张涛','周鹤洋','陈一纯','李小溪05']:
    record = load(SOURCE/(IDENTITIES[raw][1]+'.json'))['data']
    TIMELINES[raw] = sorted([(r['upgradeDate'],int(r['upgradeGrade'][1:])) for r in record['playerExperiences']])

def allowed_ranks(raw, date):
    if raw not in TIMELINES: return []
    if raw == '河灿锡' and date < '1987': return list(range(1,8))
    if raw == '村岛谊纪' and '1925' <= date < '1929': return [3,4]
    if raw == '村岛谊纪' and date.startswith('1929'): return [4,5]
    last=0; allowed=set()
    for when,rank in TIMELINES[raw]:
        prefix=date[:len(when)]
        if prefix>when: last=rank;allowed={rank}
        elif prefix==when:
            if len(when)==10: allowed.update([last,rank]);last=rank
            else: allowed.update([last,rank]);last=rank
        else: break
    return sorted(allowed-{0})

CN = dict(zip('一二三四五六七八九',range(1,10)))
def rank_number(rank):
    if not rank: return None
    if rank in ['初段','初']: return 1
    if rank in CN: return CN[rank]
    if len(rank)==2 and rank[0] in CN and rank[1] in ['段','P','p']: return CN[rank[0]]
    m=re.fullmatch(r'([1-9])(?:[pPdD]|dan|段)',rank)
    return int(m[1]) if m else None

JP = r'日本|Japanese|Japan|Meijin|Honinbo|Oza|Judan|Tengen|Gosei|Kisei|Ryusei|Ryuse|Ryūsei|NHK|Shinjin|Oteai|NihonKi-in|GoChampionship|新人王|秀行|本因坊|十段|王座|天元|名人|碁圣|棋圣|龙星|龙兴|关西|棋院|大手合|中日|新初段|关航太郎|若鲤|鯉|鲤鱼|俊英|扇兴|立葵|女流'
KR = r'韩国|Korean|Korea|KB|Wangwi|Wangui|Kukki|Kuksu|Paewang|PaeWang|Myungin|Myeongin|Guksu|Kiwang|棋王|名人|霸王|王位|国棋|国手|十段|KBS|新锐|新锐|绅士|大舟|麦馨|中国|中韩|中日韩|SBS|GS'
CN_EVT = r'中国|China|Chinese|全国|围甲|围乙|围丙|女甲|女乙|女子|个人赛|团体赛|段位赛|新人王|新秀|新锐|等级分|擂台|龙星|天元|名人|棋圣|棋王|西南|阿含|倡棋|建桥|国手|棋协|烂柯|智力|智运|国家队|NationalTeam|Promotion|Individual|Team|王中王|研讨|研究|棋圣|东北|西部|春兰|四城市|快棋|乐百氏|秀行|中日|对抗|元老|慈溪|南方|NEC|棋社|长城|三星|应氏|邀请|安庆|无锡|九龙|江苏|浙江|上海|河北|山东|平湖|杭州|山西|北京|Tianyuan|Qisheng|圣雪绒|特约指导棋|热身赛'
WORLD = r'LG|三星|Samsung|农心|Nongshim|BC|百灵|MLily|Mlily|梦百合|春兰|Chunlan|富士通|Fujitsu|应氏|Ing|亚洲|Asian|亚洲|中韩|中日|世界|World|Globi|Globis|新人王|利民|倡棋|阿含|中日韩|友谊|交流|训练|Training|AmateurPro|职业|邀请|Invitational|棋王|Masters|master|锦标|国际|杯|Cup'
EVENT_PATTERNS = {raw: re.compile((CN_EVT if raw in ['张涛','周鹤洋','陈一纯','李小溪05'] else KR if raw in ['黄宰渊','河灿锡','韩钟振'] else JP)+'|'+WORLD,re.I) for raw in IDENTITIES}

def inspect_slot(slot):
    raw=slot['raw'];aid=slot['album_id'];side=slot['side'];opp='white' if side=='black' else 'black'
    a=ALBUMS['PROD'][aid]; ident=IDENTITIES[raw]
    reasons=[]
    if ident[2] is None: reasons.append('OWNER_DUPLICATE_UNRESOLVED' if raw!='中小野田智己' else 'TRUNCATED_OWNER_COLLISION_UNRESOLVED')
    try:
        root=SGF.parse_sgf(a['sgf_content']).properties
    except Exception:
        root={};reasons.append('SGF_PARSE_ERROR')
    checks={}
    day=lambda v: v[:10] if v and re.fullmatch(r'\d{4}-\d{2}-\d{2}(?: 00:00:00)?',v) else v
    for field,prop in [('player_black','PB'),('player_white','PW'),('date_played','DT')]:
        vals=root.get(prop,[]); checks[field]={'album':a[field],'sgf':vals,'consistent':bool(vals) and all(v==a[field] for v in vals)}
        if field=='date_played': checks[field]['consistent']=bool(vals) and all(day(v)==day(a[field]) for v in vals)
        if not checks[field]['consistent']: reasons.append('SGF_'+prop+'_MISMATCH_OR_MISSING')
    for field,prop in [('black_rank','BR'),('white_rank','WR')]:
        vals=root.get(prop,[])
        if a[field] and (not vals or any(v!=a[field] for v in vals)):
            reasons.append('SGF_'+prop+'_MISMATCH_OR_MISSING')
    associations=SOURCES['PROD'][aid]
    if not associations or any(r['origin_path']!=a['source_path'] or r['source_id'] not in [1,2] for r in associations): reasons.append('SOURCE_ASSOCIATION_UNCLEAR')
    date=day(a['date_played'] or '')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) or date<'1901': reasons.append('DATE_MISSING_OR_SENTINEL')
    elif date[:len(ident[5])]<ident[5]: reasons.append('PRE_PROFESSIONAL_DATE_NEEDS_MATCH_PROOF')
    if (raw=='河灿锡' and date>'2010-09-14') or (raw=='村岛谊纪' and date>'1983-01-03'): reasons.append('DATE_AFTER_DEATH')
    rank=a[side+'_rank']; nr=rank_number(rank); allowed=allowed_ranks(raw,date)
    if rank and nr is None: reasons.append('RANK_NONSTANDARD_UNRESOLVED')
    elif nr is not None and raw in TIMELINES and nr not in allowed: reasons.append('RANK_CHRONOLOGY_CONFLICT')
    events=list(dict.fromkeys([v for v in [a['event']]+root.get('EV',[])+root.get('GN',[]) if v]))
    matched_events=[v for v in events if EVENT_PATTERNS[raw].search(v)]
    if not events: reasons.append('EVENT_CONTEXT_MISSING')
    elif not matched_events: reasons.append('EVENT_CIRCUIT_NEEDS_REVIEW')
    if not a['player_'+opp] or a['player_'+opp]==raw: reasons.append('OPPONENT_UNCLEAR')
    if not rank and a[opp+'_player_id'] is None: reasons.append('MISSING_RANK_AND_UNLINKED_OPPONENT')
    exceptions=[]
    if raw=='李小溪05' and a['player_'+opp]=='李小溪94' and aid in [3890,17877,18775,21455]:
        reasons=[r for r in reasons if r!='MISSING_RANK_AND_UNLINKED_OPPONENT']
        exceptions.append('Official CWA ranking maps exact 05/94 labels to different player numbers; this head-to-head professional women\'s game independently separates the identities.')
    if raw=='黄宰渊' and aid==79447 and side=='white':
        assert date=='2011-07-22' and a['player_black']=='李世石' and a['event']=='第39届韩国名人战预选' and a['result']=='W+R'
        reasons=[r for r in reasons if r not in ['PRE_PROFESSIONAL_DATE_NEEDS_MATCH_PROOF','RANK_NONSTANDARD_UNRESOLVED']]
        exceptions.append('KBA profile explicitly records his 2011 39th Myungin integrated-qualifier victory over Lee Sedol before 2011-08-20 professional admission; exact event/opponent/winner corroborate the amateur slot.')
    if raw=='工藤纪夫' and rank=='王座' and aid in [32910,66314]:
        reasons=[r for r in reasons if r!='RANK_NONSTANDARD_UNRESOLVED']
        exceptions.append('Nihon Ki-in records the 1977 Oza title; these 1978 title-holder labels are compatible, with Japanese professional events and opponents.')
    return {'album_id':aid,'side':side,'raw':raw,'decision':'HOLD' if reasons else 'APPROVE_EXISTING_PLAYER_FK',
            'reasons':list(dict.fromkeys(reasons)), 'target_player_id_by_environment':{'TEST':ident[2],'PROD':ident[3]} if not reasons else {'TEST':None,'PROD':None},
            'identity_source_keys':[ident[1]], 'date':date,'rank':rank,'rank_numeric':nr,'rank_allowed_by_source':allowed,
            'event':a['event'],'all_event_candidates':events,'matched_event_candidates':matched_events,'opponent_raw':a['player_'+opp], 'root_properties':root,'specific_exceptions':exceptions,
            'sgf_sha256':hashlib.sha256(a['sgf_content'].encode()).hexdigest(),'sgf_album_checks':checks,
            'environments':{env:{'album_preimage_sha256':digest(ALBUMS[env][aid]),'album_sources_preimage_sha256':digest(SOURCES[env][aid]),'before_fk':ALBUMS[env][aid][side+'_player_id'],'opponent_fk':ALBUMS[env][aid][opp+'_player_id']} for env in SNAPS}}

if __name__=='__main__':
    rows=[inspect_slot(s) for s in SNAPS['PROD']['slots']]
    (ROOT/'tmp/anchor_top20_slot_audit_astra.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    for raw in IDENTITIES:
        r=[s for s in rows if s['raw']==raw]
        print(raw,len(r),sum(s['decision']!='HOLD' for s in r),dict(collections.Counter(c for s in r for c in s['reasons'])))
    print('TOTAL',collections.Counter(s['decision'] for s in rows))
