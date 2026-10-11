import gzip,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,text,Column,JSON
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.core.models_db import KifuPlayer
# Pinned administrative image predates the existing DB pages column.
if not hasattr(KifuPlayer,'authoritative_pages'):
 KifuPlayer.authoritative_pages=Column(JSON,nullable=False)
from katrain.web.kifu.player_pages import sync_player_pages

p=Path('/work');env,phase=sys.argv[1:]
bundle=json.load(gzip.open(p/f'{env}-mixed20-unsigned-bundle.json.gz','rt'))
ids=[c['owner']['id']for c in bundle['candidates']]
assert len(ids)==len(set(ids))==20
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'])
if phase=='preview':
 with engine.connect()as conn:
  conn.execute(text('SET TRANSACTION READ ONLY'))
  rows=conn.execute(text('SELECT * FROM kifu_players WHERE id=ANY(:ids) ORDER BY id'),{'ids':ids}).mappings().all()
  old=json.loads(json.dumps({str(r['id']):dict(r)for r in rows},default=str));assert len(old)==20
 report=sync_player_pages(engine,player_ids=ids,apply=False)
 assert not report['committed'] and report['players_scanned']==20
 for change in report['changes']:
  assert change['player_id']in ids
 result={'environment':env,'phase':phase,'preimages':old,'preview':report}
elif phase=='apply':
 baseline=json.loads((p/f'{env}-pages-preview.json').read_text())
 with engine.connect()as conn:
  conn.execute(text('SET TRANSACTION READ ONLY'))
  rows=conn.execute(text('SELECT * FROM kifu_players WHERE id=ANY(:ids) ORDER BY id'),{'ids':ids}).mappings().all()
  current=json.loads(json.dumps([dict(r)for r in rows],default=str))
  assert current==[baseline['preimages'][str(i)]for i in sorted(ids)]
 report=sync_player_pages(engine,player_ids=ids,apply=True)
 assert report['committed'] and report['changes']==baseline['preview']['changes']
 result={'environment':env,'phase':phase,'report':report}
elif phase=='verify':
 baseline=json.loads((p/f'{env}-pages-preview.json').read_text())
 with engine.connect()as conn:
  conn.execute(text('SET TRANSACTION READ ONLY'))
  rows=conn.execute(text('SELECT * FROM kifu_players WHERE id=ANY(:ids) ORDER BY id'),{'ids':ids}).mappings().all()
  for raw in rows:
   row=json.loads(json.dumps(dict(raw),default=str))
   old=baseline['preimages'][str(row['id'])]
   assert {k:v for k,v in row.items()if k!='authoritative_pages'}=={k:v for k,v in old.items()if k!='authoritative_pages'}
   by_url={r['url']:r for r in row['authoritative_pages']}
   for original in old['authoritative_pages']:
    current=by_url[original['url']]
    assert {k:v for k,v in current.items()if k!='evidence_ids'}=={k:v for k,v in original.items()if k!='evidence_ids'}
    assert set(original.get('evidence_ids',[]))<=set(current.get('evidence_ids',[]))
 report=sync_player_pages(engine,player_ids=ids,apply=False)
 assert report['players_changed']==report['pages_added']==0 and not report['changes']
 result={'environment':env,'phase':phase,'passed':True,'players_checked':len(rows),'report':report}
else:raise SystemExit('bad phase')
engine.dispose()
print(json.dumps(result,ensure_ascii=False,sort_keys=True,default=str))
