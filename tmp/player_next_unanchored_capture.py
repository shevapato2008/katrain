import gzip, hashlib, json, subprocess, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
top20 = {x['raw'] for x in json.loads((ROOT/'docs/resource/kifu-player-exact-anchor-top20-research-2026-10-04.json').read_text())['entries']}
safe6 = {x['raw'] for x in json.loads((ROOT/'docs/resource/kifu-player-safe6-independent-exact-slot-decision-astra-2026-10-04.json').read_text())['identities']}
holds = set()
for p in ROOT.glob('docs/resource/*identity-research*.json'):
    try:
        d=json.loads(p.read_text())
        for x in d.get('entries',[]):
            if str(x.get('status','')).startswith('HOLD'):
                holds.add(x.get('raw'))
    except Exception:
        pass
known_excluded = {x for x in top20|safe6|holds if x}

REMOTE = r'''
import datetime,gzip,hashlib,json,os,unicodedata
from sqlalchemy import create_engine,text
CONFIG=__CONFIG__
def enc(v):
    if isinstance(v,dict):return {k:enc(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [enc(x) for x in v]
    if hasattr(v,'isoformat'):return v.isoformat()
    return v
def key(v):
    return ''.join(c for c in unicodedata.normalize('NFKC',v).casefold() if not c.isspace() and not unicodedata.category(c).startswith('P'))
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
e=create_engine(os.environ['KATRAIN_DATABASE_URL'])
with e.connect() as c:
 c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
 db=c.scalar(text('select current_database()'))
 def rows(table,where='',params=None,order='id'):
  return [enc(dict(r)) for r in c.execute(text('select * from '+table+(' where '+where if where else '')+' order by '+order),params or {}).mappings()]
 catalog={t:rows(t) for t in ('kifu_players','kifu_player_aliases','kifu_player_names')}
 owners={}
 for t,fields,of in [('kifu_players',['canonical_name'],'id'),('kifu_player_aliases',['alias','normalized_alias'],'player_id'),('kifu_player_names',['display_name'],'player_id')]:
  for r in catalog[t]:
   for f in fields:
    if r.get(f):owners.setdefault(key(r[f]),set()).add(r[of])
 rawrows=rows('kifu_raw_player_values')
 cands=[]
 for r in rawrows:
  raw=r['raw_value']; pd=r.get('parsed_data') or {}; cat=r.get('category')
  if cat!='readable_unlinked' or not raw or key(raw) in owners: continue
  slots=c.execute(text('select count(*) from kifu_albums where (player_black=:r and black_player_id is null) or (player_white=:r and white_player_id is null)'),{'r':raw}).scalar_one()
  if slots: cands.append({'raw':raw,'slots':slots,'category':cat,'parsed_data':pd})
 cands.sort(key=lambda x:(-x['slots'],x['raw'].encode()))
 selected=cands[:35]
 selected_raw=[x['raw'] for x in selected]
 albums=rows('kifu_albums','((player_black=any(:raws) and black_player_id is null) or (player_white=any(:raws) and white_player_id is null))',{'raws':selected_raw})
 slots=[]
 for a in albums:
  for side in ('black','white'):
   raw=a['player_'+side]
   if raw in selected_raw and a[side+'_player_id'] is None:
    slots.append({'album_id':a['id'],'side':side,'raw':raw,'opponent_raw':a['player_'+('white' if side=='black' else 'black')],'opponent_fk':a[('white' if side=='black' else 'black')+'_player_id'],'full_album':a,'album_sha256':digest(a)})
 # compact safe subset: highest 8 with a Wikimedia/official style identity lead supplied later
 safe=selected[:8]; safe_raw=[x['raw'] for x in safe]
 safe_albums=[x for x in slots if x['raw'] in safe_raw]
 srcids=sorted({a.get('source_id') for a in safe_albums if a.get('source_id') is not None})
 source_rows=rows('kifu_album_sources','album_id=any(:ids)',{'ids':[a['album_id'] for a in safe_albums]}) if safe_albums else []
 sgf=[{'album_id':a['album_id'],'sgf_content':a['full_album'].get('sgf_content'),'source_path':a['full_album'].get('source_path'),'content_sha256':hashlib.sha256((a['full_album'].get('sgf_content') or '').encode()).hexdigest()} for a in safe_albums]
 out={'format':'kifu-player-next-unanchored-readonly-preimage-v1','environment':CONFIG['environment'],'database':db,'captured_at_db_utc':enc(c.scalar(text('select now()'))),'read_only':True,'transaction_isolation':c.scalar(text('show transaction_isolation')),'transaction_read_only':c.scalar(text('show transaction_read_only')),'excluded_inputs':CONFIG['excluded'],'catalog_owner_key_count':len(owners),'candidates':selected,'candidate_total_null_slots':sum(x['slots'] for x in selected),'safe_subset_raws':safe_raw,'safe_subset_slots':safe_albums,'safe_subset_sources':source_rows,'safe_subset_sgf_preimages':sgf,'catalog':catalog,'global_counts':enc(dict(c.execute(text('select count(*) as games,count(black_player_id)+count(white_player_id) as player_links from kifu_albums')).mappings().one()))}
 assert out['transaction_read_only']=='on'
 print(gzip.compress(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(),mtime=0).hex())
 e.dispose()
'''

def capture(env, host, container, database):
    cfg={'environment':env,'database':database,'excluded':{'top20':sorted(top20),'safe6':sorted(safe6),'holds':sorted(holds)}}
    code=REMOTE.replace('__CONFIG__',repr(cfg))
    p=subprocess.run(['ssh',host,'docker','exec','-i',container,'python','-'],input=code.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    raw=bytes.fromhex(p.stdout.decode().strip())
    return json.loads(gzip.decompress(raw)),raw

if __name__=='__main__':
    out={}
    for env,host,container,db in [('test','home-ubuntu','katrain-web','katrain_db'),('prod','ucloud-v100','katrain-ucloud-katrain-web-1','katrain_prod_20260725')]:
        d,raw=capture(env,host,container,db); out[env]={'doc':d,'raw':raw.hex(),'sha256':hashlib.sha256(raw).hexdigest()}
    path=ROOT/'tmp/player-next-unanchored-live.json'
    path.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True))
    print(json.dumps({k:{'sha256':v['sha256'],'candidates':len(v['doc']['candidates']),'slots':v['doc']['candidate_total_null_slots']} for k,v in out.items()},ensure_ascii=False))
