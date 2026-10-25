import asyncio,collections,datetime,hashlib,json,logging,time
from pathlib import Path
from sqlalchemy import select,func
from katrain.cron import config
from katrain.cron.db import engine,SessionLocal
from katrain.cron.run_recorder import RunRecorder
from katrain.cron.jobs.kifu_ingest import KifuIngestJob
from katrain.web.core.models_db import KifuAlbum,KifuPlayerRankHistory,KifuAlbumRankSnapshot
root=Path(config.KIFU_INGEST_STAGING_DIR)
ids=['7923089','7926016','7928067','7928304','7929649','7929673','7929683']
def before_after():
 j=json.loads((root/'manifest.json').read_text())
 ledger=root/('qwen-usage-'+datetime.datetime.now(datetime.timezone.utc).date().isoformat()+'.json')
 with engine.connect() as c:
  counts={m.__tablename__:c.scalar(select(func.count()).select_from(m)) for m in (KifuAlbum,KifuPlayerRankHistory,KifuAlbumRankSnapshot)}
 return {'rolling_cursor':j.get('rolling_cursor'),'legacy_7004':{i:{k:j['items'].get(i,{}).get(k) for k in ('attempts','status','last_error')} for i in ids},'head':j.get('head'),'counts':counts,'ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest() if ledger.exists() else None}
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(message)s')
async def main():
 before=before_after(); started=time.monotonic();rec=RunRecorder(SessionLocal);rec._intervals['kifu_ingest']=config.KIFU_INGEST_INTERVAL
 await rec.run(KifuIngestJob())
 after=before_after(); result={'status':'completed','elapsed_seconds':round(time.monotonic()-started,2),'before':before,'after':after,'rolling_unchanged':before['rolling_cursor']==after['rolling_cursor'],'legacy_attempts_unchanged':before['legacy_7004']==after['legacy_7004'],'token_ledger_unchanged':before['ledger_sha256']==after['ledger_sha256'],'effective_config':{k:getattr(config,k) for k in ('KIFU_INGEST_ENABLED','KIFU_INGEST_INTERVAL','KIFU_INGEST_WINDOW_DAYS','KIFU_INGEST_HEAD_PAGES','KIFU_INGEST_MAX_REQUESTS','KIFU_INGEST_MAX_GAMES','KIFU_INGEST_SOURCE_SECONDS','KIFU_INGEST_RECOVERY_SECONDS','KIFU_INGEST_TOTAL_SECONDS','KIFU_INGEST_MAX_TOKENS')}}
 assert result['rolling_unchanged'] and result['legacy_attempts_unchanged']
 (root/'rank-corrections/source-round-result.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True))
 print(json.dumps({k:v for k,v in result.items() if k not in ('before','after')},ensure_ascii=False))
asyncio.run(main())
