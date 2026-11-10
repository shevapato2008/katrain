"""Restore only our maintenance pause after actual corrected72 two-cloud verification."""
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import select,func
from katrain.cron.db import engine
from katrain.cron.models import CronJobControlDB,CronJobCommandDB,CronJobRunDB
from katrain.cron.jobs.kifu_ingest import _session_lock
from katrain.kifu_ingest.state import batches,items
from katrain.kifu_ingest.sync import validate_test_verification
from katrain.web.kifu.name_candidates import canonical_sha256

root=Path('/app/data/kifu_ingest')
actor='codex-hourly-recovery-20261020'
key='19x19-event-recovery-870a06d9f6b3f234b354a5f4'
digest='0f64c2b366a0d9ba59b452d4aac4148dc5609d19c57c6befa1deacde06459e67'
assert os.environ['KATRAIN_BUILD_SHA']=='e23ac4105ad6ec770c4ebedf03e389b20768ee6c'
manifest=json.loads((root/'packages/91315699-0f64c2b366a0d9ba.json').read_text())
assert canonical_sha256(manifest)==digest
with _session_lock(engine) as acquired:
    assert acquired,'another ingest writer is active'
    with engine.begin() as conn:
        row=conn.execute(select(batches).where(batches.c.publication_key==key).with_for_update()).mappings().one()
        assert row['status']=='prod_synced' and row['manifest_sha256']==digest
        for field in ['test_verification','prod_verification']:
            validate_test_verification(manifest,digest,row[field])
        expected={g['source_item_id'] for g in manifest['games']}
        receipts={field:{g['source_item_id']:g['album_id'] for g in row[field]['games']} for field in ['test_receipt','prod_receipt']}
        assert all(set(ids)==expected for ids in receipts.values())
        rows=conn.execute(select(items).where(items.c.publication_key==key).with_for_update()).mappings().all()
        assert len(rows)==72 and {r['external_id'] for r in rows}==expected
        assert all(r['status']=='prod_synced' and r['test_album_id']==receipts['test_receipt'][r['external_id']] and r['prod_album_id']==receipts['prod_receipt'][r['external_id']] for r in rows)
        ctrl=conn.execute(select(CronJobControlDB.__table__).where(CronJobControlDB.job_name=='kifu_ingest').with_for_update()).mappings().one()
        assert ctrl['paused'] and ctrl['changed_by']==actor
        assert not conn.scalar(select(func.count()).select_from(CronJobRunDB).where(CronJobRunDB.job_name=='kifu_ingest',CronJobRunDB.status=='running'))
        assert not conn.scalar(select(func.count()).select_from(CronJobCommandDB).where(CronJobCommandDB.job_name=='kifu_ingest',CronJobCommandDB.state=='pending'))
        previous=json.loads((root/'hourly-recovery-control-before.json').read_text())
        if previous is None:
            result=conn.execute(CronJobControlDB.__table__.delete().where(CronJobControlDB.job_name=='kifu_ingest',CronJobControlDB.changed_by==actor));assert result.rowcount==1
        else:
            assert previous['paused'] is False
            previous['changed_at']=datetime.fromisoformat(previous['changed_at'])
            conn.execute(CronJobControlDB.__table__.update().where(CronJobControlDB.job_name=='kifu_ingest').values(**previous))
        command=conn.execute(CronJobCommandDB.__table__.insert().values(job_name='kifu_ingest',command='run_now',requested_at=datetime.now(timezone.utc),requested_by=actor,state='pending').returning(CronJobCommandDB.id)).scalar_one()
print(json.dumps({'maintenance_pause_restored':True,'command_id':command,'verified_games':72,'checks_per_environment':360,'no_publication_phase_modified':True}))
