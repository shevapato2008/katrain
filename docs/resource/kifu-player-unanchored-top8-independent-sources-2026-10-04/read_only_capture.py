import json,os,hashlib
from datetime import datetime,date
from sqlalchemy import create_engine,text
RAWS=['姜勋','Iwamoto Kaoru','Maeda Nobuaki','林彦丞','王尧','Fujisawa Hosai','蔡竞','Yoshida Yoichi']
CANDIDATES=['岩本熏','岩本薫','岩本薰','前田陈尔','前田陳爾','前田陈二','吉田阳一','吉田陽一','林彦丞','林彥丞','王尧','王尭','王垚','蔡竞','蔡竟','姜勋','姜勳','藤沢库之助','藤泽库之助','藤泽朋斋','藤泽朋斎','藤沢朋斎','藤澤朋齋']
def rows(c,s,p=None):
 return [{k:v.isoformat() if isinstance(v,(date,datetime)) else v for k,v in r.items()} for r in c.execute(text(s),p or {}).mappings()]
def h(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
e=create_engine(os.environ['KATRAIN_DATABASE_URL'])
with e.connect() as c:
 c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
 catalogs=rows(c,'SELECT * FROM kifu_players ORDER BY id'); aliases=rows(c,'SELECT * FROM kifu_player_aliases ORDER BY id'); names=rows(c,'SELECT * FROM kifu_player_names ORDER BY id')
 candidate_ids=sorted({x['id'] for x in catalogs if x['canonical_name'] in CANDIDATES})
 albums=rows(c,'SELECT * FROM kifu_albums WHERE black_player_id=ANY(:ids) OR white_player_id=ANY(:ids) OR player_black=ANY(:raws) OR player_white=ANY(:raws) ORDER BY id',{'ids':candidate_ids,'raws':RAWS+CANDIDATES})
 album_ids=[a['id'] for a in albums]
 album_sources=rows(c,'SELECT * FROM kifu_album_sources WHERE album_id=ANY(:ids) ORDER BY id',{'ids':album_ids})
 source_ids=sorted({x['source_id'] for x in album_sources})
 sources=rows(c,'SELECT * FROM kifu_sources WHERE id=ANY(:ids) ORDER BY id',{'ids':source_ids})
 data={'format':'kifu-player-unanchored-top8-supplemental-readonly-v1','read_only':True,'database':c.scalar(text('SELECT current_database()')),'snapshot':c.scalar(text('SELECT txid_current_snapshot()::text')),'captured_at_utc':c.scalar(text('SELECT clock_timestamp()::text')),'candidate_names':CANDIDATES,'candidate_ids':candidate_ids,'catalog':catalogs,'aliases':aliases,'names':names,'albums':albums,'album_sources':album_sources,'sources':sources,'raw_staging':rows(c,'SELECT * FROM kifu_raw_player_values WHERE raw_value=ANY(:raws) ORDER BY id',{'raws':RAWS+CANDIDATES})}
 data['content_hashes']={k:h(data[k]) for k in ['catalog','aliases','names','albums','album_sources','sources','raw_staging']}
 print(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')))
e.dispose()
