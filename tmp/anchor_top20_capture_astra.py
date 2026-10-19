"""Read-only exact-name player review capture; secrets stay inside containers."""
import concurrent.futures
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
research = json.loads((ROOT / 'docs/resource/kifu-player-exact-anchor-top20-research-2026-10-04.json').read_text())
raws = [r['raw'] for r in research['entries']]
variants = {
    '张涛': ['张涛', '張濤', 'Zhang Tao', 'Tao Zhang'],
    '韩升周': ['韩升周', '韩昇周', '韓昇周', '韓升周', '한승주', 'Han Seungju', 'Han Seung-ju', 'Han Seung Joo'],
    '奥田彩': ['奥田彩', '奥田あや', 'Aya Okuda', 'Okuda Aya'],
    '工藤纪夫': ['工藤纪夫', '工藤紀夫', 'Norio Kudo', 'Kudo Norio', 'Norio Kudō'],
    '周鹤洋': ['周鹤洋', '周鶴洋', 'Zhou Heyang', 'Heyang Zhou'],
    '中小野田智己': ['中小野田智己', 'Tomomi Nakaonoda', 'Nakaonoda Tomomi'],
    '鹤田和志': ['鹤田和志', '鶴田和志', 'Kazushi Tsuruta', 'Tsuruta Kazushi'],
    '姚智腾': ['姚智腾', '姚智騰', 'Yao Zhiteng', 'Zhiteng Yao'],
    '谷口彻': ['谷口彻', '谷口徹', 'Toru Taniguchi', 'Taniguchi Toru', 'Tooru Taniguchi'],
    '赵善津': ['赵善津', '趙善津', '조선진', 'Cho Sonjin', 'Cho Son-jin', 'Cho Son Jin'],
    '辻笃仁': ['辻笃仁', '辻篤仁', 'Atsuhito Tsuji', 'Tsuji Atsuhito'],
    '黄宰渊': ['黄宰渊', '黃宰淵', '황재연', 'Hwang Jaeyeon', 'Hwang Jae-yeon', 'Hwang Jae Yeon'],
    '横塚力': ['横塚力', '橫塚力', 'Riki Yokotsuka', 'Yokotsuka Riki'],
    '陈一纯': ['陈一纯', '陳一純', 'Chen Yichun', 'Yichun Chen', 'Chen I-chun'],
    '田中康湧': ['田中康湧', '田中康涌', 'Koyu Tanaka', 'Tanaka Koyu', 'Kouyuu Tanaka'],
    '河灿锡': ['河灿锡', '河燦錫', '河灿钖', '하찬석', 'Ha Chanseok', 'Ha Chan-seok', 'Ha Chan Seok'],
    '久保胜昭': ['久保胜昭', '久保勝昭', 'Katsuaki Kubo', 'Kubo Katsuaki'],
    '李小溪05': ['李小溪05', '李小溪', 'Li Xiaoxi', 'Xiaoxi Li', '李小溪(05)', '李小溪（05）'],
    '韩钟振': ['韩钟振', '韓鐘振', '韓鍾振', '韩钟震', '한종진', 'Han Jongjin', 'Han Jong-jin', 'Han Jong Jin'],
    '村岛谊纪': ['村岛谊纪', '村島誼紀', '村島誼紀', 'Yoshiki Murashima', 'Murashima Yoshiki'],
}

REMOTE = r'''
import datetime,gzip,hashlib,json,os,sys,unicodedata
from sqlalchemy import create_engine,text
CONFIG = __CONFIG__
def enc(v):
    if isinstance(v,dict): return {k:enc(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [enc(x) for x in v]
    if hasattr(v,'isoformat'): return v.isoformat()
    return v
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def key(v):return ''.join(c for c in unicodedata.normalize('NFKC',v).casefold() if not c.isspace() and not unicodedata.category(c).startswith('P'))
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'])
with engine.connect() as c:
    c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
    def rows(table,where='',params=None):
        return [enc(dict(r)) for r in c.execute(text('SELECT * FROM '+table+(' WHERE '+where if where else '')+' ORDER BY id'),params or {}).mappings()]
    database=c.execute(text('SELECT current_database()')).scalar_one()
    if database != CONFIG['database']: raise RuntimeError('Unexpected database')
    catalog={'players':rows('kifu_players'),'aliases':rows('kifu_player_aliases'),'names':rows('kifu_player_names')}
    owner_hits={}
    for raw,variants in CONFIG['variants'].items():
        keys={key(s) for s in variants};hits=[]
        for table,fields,owner_field in [('players',['canonical_name'],'id'),('aliases',['alias','normalized_alias'],'player_id'),('names',['display_name'],'player_id')]:
            for row in catalog[table]:
                matched=[f for f in fields if row.get(f) and key(row[f]) in keys]
                if matched:hits.append({'table':table,'row_id':row['id'],'owner_id':row[owner_field],'matched_fields':matched,'row':row,'row_sha256':digest(row)})
        owner_hits[raw]=hits
    owner_ids=sorted({r['owner_id'] for hits in owner_hits.values() for r in hits})
    raws=CONFIG['raws']
    albums=rows('kifu_albums','(player_black=ANY(:raws) AND black_player_id IS NULL) OR (player_white=ANY(:raws) AND white_player_id IS NULL)',{'raws':raws})
    slots=[]
    for a in albums:
        for side,opp in [('black','white'),('white','black')]:
            if a['player_'+side] in raws and a[side+'_player_id'] is None:
                slots.append({'album_id':a['id'],'side':side,'raw':a['player_'+side],'current_fk':None,'opponent_raw':a['player_'+opp],'opponent_fk':a[opp+'_player_id']})
    slots=sorted(slots,key=lambda r:(r['album_id'],r['side']))
    album_ids=[r['id'] for r in albums]
    context=rows('kifu_albums','black_player_id=ANY(:owners) OR white_player_id=ANY(:owners) OR player_black=ANY(:raws) OR player_white=ANY(:raws)',{'owners':owner_ids,'raws':raws})
    context_ids=[r['id'] for r in context]
    out={'format':'kifu-player-anchor-top20-full-readonly-preimage-astra-v1','environment':CONFIG['environment'],'database':database,
         'captured_at_db_utc':enc(c.execute(text('SELECT now()')).scalar_one()),'read_only':True,
         'transaction_isolation':c.execute(text('SHOW transaction_isolation')).scalar_one(),
         'transaction_read_only':c.execute(text('SHOW transaction_read_only')).scalar_one(),
         'raws':raws,'variant_scan_inputs':CONFIG['variants'],'owner_hits':owner_hits,'albums':albums,'slots':slots,
         'album_sources':rows('kifu_album_sources','album_id=ANY(:ids)',{'ids':album_ids}),
         'sources':rows('kifu_sources'),'events':rows('kifu_events'),'event_editions':rows('kifu_event_editions'),
         'event_aliases':rows('kifu_event_aliases'),'catalog':catalog,
         'raw_staging':rows('kifu_raw_player_values','raw_value=ANY(:raws)',{'raws':raws}),
         'existing_owner_context':{'owner_ids':owner_ids,'albums':context,'album_sources':rows('kifu_album_sources','album_id=ANY(:ids)',{'ids':context_ids})},
         'global_counts':dict(c.execute(text('SELECT count(*) AS games, count(black_player_id)+count(white_player_id) AS player_links, count(event_id) AS event_links FROM kifu_albums')).mappings().one())}
    assert out['transaction_read_only']=='on'
    sys.stdout.buffer.write(gzip.compress(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(),mtime=0))
    c.rollback()
engine.dispose()
'''

def capture(environment,host,container,database,suffix=''):
    config={'environment':environment,'database':database,'raws':raws,'variants':variants}
    code=REMOTE.replace('__CONFIG__',repr(config))
    result=subprocess.run(['ssh',host,'docker','exec','-i',container,'python','-'],input=code.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if result.returncode:
        raise RuntimeError(f'{environment}: capture failed (stderr intentionally suppressed to avoid credentials)')
    doc=json.loads(gzip.decompress(result.stdout))
    path=ROOT / f'docs/resource/kifu-player-exact-anchor-top20-{environment.upper()}{suffix}-full-preimage-astra-2026-10-04.json.gz'
    if path.exists():raise RuntimeError('Immutable path already exists')
    path.write_bytes(result.stdout)
    sha=hashlib.sha256(result.stdout).hexdigest()
    path.with_name(path.name+'.sha256').write_text(sha+'  '+path.name+'\n')
    return {'environment':environment,'path':str(path.relative_to(ROOT)),'sha256':sha,'albums':len(doc['albums']),'slots':len(doc['slots']),'existing_context_albums':len(doc['existing_owner_context']['albums']),'owners':doc['existing_owner_context']['owner_ids'],'counts':doc['global_counts']}

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(capture,'test','home-ubuntu','katrain-web','katrain_db'),pool.submit(capture,'prod','ucloud-v100','katrain-ucloud-katrain-web-1','katrain_prod_20260725')]
        for task in tasks:print(json.dumps(task.result(),ensure_ascii=False))
