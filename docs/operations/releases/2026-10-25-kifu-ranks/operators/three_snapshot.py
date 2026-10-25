import hashlib,json,sys,datetime
from pathlib import Path
from sqlalchemy import create_engine,select,func
from katrain.web.core.models_db import KifuAlbum,KifuAlbumSource,KifuNameBatch,KifuPlayerRankHistory,KifuAlbumRankSnapshot
from katrain.web.kifu.name_candidates import canonical_sha256
kind=sys.argv[1]
if kind=='test':
 from katrain.cron.db import engine
 ids=[179093,179085,179084]
else:
 from katrain.web.core.config import settings
 engine=create_engine(settings.DATABASE_URL)
 ids=[178757,178749,178748]
digests=['0dbd77cb3a4290768ad9955542a51a8dc85cc6517231a0778faf06b42417d8fb','2608c873a1f62fade6f3e5b5964befb69e43d32009920c3a7793c3c198920e1e','c14e011c14dbca7511ae472e0c70c0f3fda4f0cb3ef2ba42e7dbe348de924824']
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(datetime.datetime,datetime.date)):return x.isoformat()
 return x
with engine.connect() as c:
 c.exec_driver_sql('SET TRANSACTION READ ONLY');c.exec_driver_sql("SET LOCAL statement_timeout='8s'")
 rows=[dict(x) for x in c.execute(select(KifuAlbum.__table__).where(KifuAlbum.id.in_(ids)).order_by(KifuAlbum.id)).mappings()]
 albums=[]
 for r in rows:
  r['sgf_sha256']=hashlib.sha256(r.pop('sgf_content').encode()).hexdigest();albums.append(clean(r))
 links=clean([dict(r) for r in c.execute(select(KifuAlbumSource.__table__).where(KifuAlbumSource.album_id.in_(ids)).order_by(KifuAlbumSource.id)).mappings()])
 old=[]
 for r in c.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256.in_(digests)).order_by(KifuNameBatch.id)).mappings():
  x=dict(r);x['artifact_sha256']=canonical_sha256(x.pop('reviewed_artifact'));old.append(clean(x))
 ranks=clean([dict(r) for r in c.execute(select(KifuAlbumRankSnapshot.__table__).where(KifuAlbumRankSnapshot.album_id.in_(ids)).order_by(KifuAlbumRankSnapshot.id)).mappings()])
 count=c.scalar(select(func.count()).select_from(KifuAlbum))
 rank_count=c.scalar(select(func.count()).select_from(KifuPlayerRankHistory))
 snap_count=c.scalar(select(func.count()).select_from(KifuAlbumRankSnapshot))
 result={'target':kind,'album_count':count,'albums':albums,'source_links':links,'original_native_batches':old,'rank_history_count':rank_count,'rank_snapshot_count':snap_count,'rank_snapshots':ranks}
 if kind=='test':
  from katrain.kifu_ingest.state import items
  states=clean([dict(r) for r in c.execute(select(items).where(items.c.external_id.in_(['91694911','91638738','91637528'])).order_by(items.c.external_id)).mappings()])
  result['original_item_states']=[{k:r.get(k) for k in ('external_id','status','publication_key','test_album_id','prod_album_id')}|{'row_sha256':canonical_sha256(r)} for r in states]
if kind=='test':
 root=Path('/app/data/kifu_ingest');names=['manifest.json','packages/91694911-0dbd77cb3a429076.json','packages/91638738-2608c873a1f62fad.json','packages/91634842-c14e011c14dbca75.json','qwen-usage-'+datetime.datetime.now(datetime.timezone.utc).date().isoformat()+'.json']
 result['protected_files_sha256']={n:hashlib.sha256((root/n).read_bytes()).hexdigest() if (root/n).is_file() else None for n in names}
print(json.dumps(result,ensure_ascii=False,sort_keys=True))
