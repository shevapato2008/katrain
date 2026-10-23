"""Archive only the two exact pre-correction API proofs; retain every byte."""
import hashlib,json,os,pathlib
from datetime import datetime,timezone
from sqlalchemy import select,text
from katrain.cron import config
from katrain.cron.db import engine
from katrain.cron.jobs.kifu_ingest import _session_lock
from katrain.cron.models import CronJobControlDB
from katrain.kifu_ingest.staging import staging_writer_lock,Stage
from katrain.kifu_ingest.state import batches
from katrain.kifu_ingest.verification import normalized_target
from katrain.web.kifu.name_candidates import canonical_sha256
root=pathlib.Path('/app/data/kifu_ingest');destination=root/'name-correction-20261024'/'pre-correction-checkpoints';audit_path=destination.parent/'checkpoint-archive-audit.json'
manifest_sha='57a579a34b83134e7cca5fa51836e3cea4dfa69b00177d3cdf50abd4668a60c5'
with _session_lock(engine) as acquired:
 assert acquired
 with staging_writer_lock(root):
  with engine.connect() as c:
   c.execute(text('SET TRANSACTION READ ONLY'));assert c.scalar(select(CronJobControlDB.paused).where(CronJobControlDB.job_name=='kifu_ingest')) is True
   row=c.execute(select(batches).where(batches.c.manifest_sha256==manifest_sha)).mappings().one();assert row['status']=='prod_synced'
  expected={normalized_target(config.KIFU_INGEST_TEST_API_URL):canonical_sha256(row['test_receipt']),normalized_target(config.KIFU_INGEST_PROD_API_URL):canonical_sha256(row['prod_receipt'])}
  assert len(expected)==2 and not destination.is_symlink();destination.mkdir(parents=True,exist_ok=True)
  atomic=Stage(root)._atomic
  if audit_path.exists():
   audit=json.loads(audit_path.read_text());assert audit['manifest_sha256']==manifest_sha and audit['expected_receipt_hashes']==expected
  else:
   entries=[]
   for path in (root/'api-verification').glob('*.json'):
    assert not path.is_symlink();raw=path.read_bytes();doc=json.loads(raw);binding=doc['binding']
    if binding['manifest_sha256']!=manifest_sha:continue
    assert binding['target'] in expected and binding['receipt_sha256']==expected[binding['target']]
    assert path.stem==canonical_sha256(binding) and len(doc['completed'])==10
    assert doc['content_sha256']==canonical_sha256({k:v for k,v in doc.items() if k!='content_sha256'})
    entries.append({'source':str(path),'archive':str(destination/path.name),'raw_sha256':hashlib.sha256(raw).hexdigest(),'binding':binding,'completed_albums':len(doc['completed'])})
   assert len(entries)==2 and {e['binding']['target'] for e in entries}==set(expected)
   audit={'operation':'archive exact pre-name-correction successful API checkpoints; not deletion','manifest_sha256':manifest_sha,'expected_receipt_hashes':expected,'created_at':datetime.now(timezone.utc).isoformat(),'phase':'planned','entries':entries}
   atomic(audit_path,json.dumps(audit,indent=2,sort_keys=True).encode())
  for item in audit['entries']:
   source=pathlib.Path(item['source']);archive=pathlib.Path(item['archive'])
   assert source.parent==root/'api-verification' and archive.parent==destination and source.name==archive.name
   if archive.exists():
    assert not source.exists() and not archive.is_symlink() and hashlib.sha256(archive.read_bytes()).hexdigest()==item['raw_sha256']
   else:
    assert source.exists() and not source.is_symlink() and hashlib.sha256(source.read_bytes()).hexdigest()==item['raw_sha256']
    source.rename(archive)
    assert not source.exists() and hashlib.sha256(archive.read_bytes()).hexdigest()==item['raw_sha256']
   item['archived']=True;audit['phase']='moving';atomic(audit_path,json.dumps(audit,indent=2,sort_keys=True).encode())
  audit['phase']='complete';audit['completed_at']=datetime.now(timezone.utc).isoformat();atomic(audit_path,json.dumps(audit,indent=2,sort_keys=True).encode())
print(json.dumps(audit,indent=2,sort_keys=True))
