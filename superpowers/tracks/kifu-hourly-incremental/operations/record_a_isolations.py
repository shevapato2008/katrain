"""TEST-only operator tool: remember reviewed A isolations without touching Stage/catalog.

Default dry-run. Run only after A completes, with B disabled; CLI holds B's existing
PostgreSQL session lock across all preflight reads and public StateStore writes.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from sqlalchemy import select

from katrain.kifu_ingest.state import StateStore, items
from katrain.web.core.models_db import KifuNameBatch

REPORT_SHA='42f335c6a65b1ca8e87defe359a8a32927b3358033158eb3a39e127273e4bc88'
PROTECTED={'91346707','91358273','91315699','91317146','91346493'}
EMPTY_FIELDS=('raw_sha256','sgf_sha256','staging_path','publication_key','test_album_id','prod_album_id',
              'test_receipt','test_verification','prod_receipt','prod_verification')

class SafetyError(ValueError):
    pass

def require(condition,message):
    if not condition:raise SafetyError(message)

def numeric(value):
    require(isinstance(value,str) and re.fullmatch(r'[0-9]+',value) is not None,'invalid source ID')
    return value

def read_json(path):
    require(path.is_file() and not path.is_symlink(),'required JSON file missing or symlinked')
    return json.loads(path.read_text(encoding='utf-8'))

def provenance(record):
    return {'a_isolation':{'report_sha256':REPORT_SHA,'raw_sha256':record['raw_sha256'],
            'sgf_sha256':record['sgf_sha256'],'reason_codes':record['reason_codes'],'issues':record['issues']}}

def load_report(path):
    require(path.is_file() and not path.is_symlink(),'required report missing or symlinked')
    raw=path.read_bytes()
    require(sha256(raw).hexdigest()==REPORT_SHA,'fixed isolation report SHA mismatch')
    report=json.loads(raw)
    summary=report['summary'];records=report['records']
    require(report['schema_version']=='a-isolation-report-v1' and summary['source_key']=='19x19','wrong report schema/source')
    require((summary['inventory_records'],summary['ready_package_records'],summary['ready_package_count'],summary['unique_isolated_records'])==(5536,5279,55,257),'wrong reviewed partition counts')
    ids=[numeric(r['source_item_id']) for r in records]
    require(len(ids)==len(set(ids))==257 and set(ids)==set(report['isolated_source_ids']),'report is not 257 unique identities')
    require(not set(ids)&PROTECTED,'report overlaps protected B items')
    require(len(report['verified_ready_packages'])==55 and sum(p['games'] for p in report['verified_ready_packages'])==5279,'wrong ready package accounting')
    for key in ['ready_and_isolated_disjoint','ready_union_isolated_equals_inventory','all_55_package_file_hashes_match_frozen_records']:
        require(report['reconciliation'][key] is True,'reviewed partition reconciliation missing')
    for record in records:
        require(record['source_key']=='19x19','wrong record source')
        require(all(isinstance(record[k],str) and re.fullmatch(r'[0-9a-f]{64}',record[k]) for k in ['raw_sha256','sgf_sha256']),'invalid original hash')
        require(isinstance(record['reason_codes'],list) and record['reason_codes'] and all(isinstance(v,str) and v for v in record['reason_codes']) and isinstance(record['issues'],list) and record['issues'],'missing isolation reason')
    return records

def operate(engine,root,report_path,*,apply=False):
    """Caller holds the session lock; SQLite tests exercise this body in isolation."""
    records=load_report(Path(report_path));ids={r['source_item_id'] for r in records};root=Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(),'invalid existing Stage root')
    manifest=read_json(root/'manifest.json')
    require(manifest['source_key']=='19x19' and isinstance(manifest['items'],dict),'invalid Stage manifest')
    staged=set()
    for key,entry in manifest['items'].items():
        require(numeric(key)==numeric(entry['external_id']) and entry['source_key']=='19x19','invalid Stage identity')
        staged.add(key)
    require(not ids&staged,'Stage overlap with isolation IDs')
    packages=root/'packages';packaged=set()
    require(not packages.is_symlink(),'symlinked package directory')
    if packages.exists():
        require(packages.is_dir(),'invalid package directory')
        for path in sorted(packages.rglob('*')):
            require(not path.is_symlink(),'symlinked package input')
            if path.is_file() and path.suffix=='.json':
                package=read_json(path)
                require(isinstance(package.get('games'),list),'invalid frozen package games')
                for game in package['games']:
                    require(game['source_key']=='19x19','wrong frozen package source')
                    packaged.add(numeric(game['source_item_id']))
    require(not ids&packaged,'frozen package overlap with isolation IDs')
    with engine.connect() as conn:
        existing={r['external_id']:dict(r) for r in conn.execute(select(items).where(items.c.source_key=='19x19',items.c.external_id.in_(ids))).mappings()}
        native=set()
        for artifact in conn.scalars(select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.status=='applied',KifuNameBatch.reviewed_artifact['publication_format'].as_string()=='kifu-incremental-manifest-v1')):
            if isinstance(artifact,dict) and artifact.get('publication_format')=='kifu-incremental-manifest-v1':
                require(isinstance(artifact.get('sources'),list),'invalid applied native source receipts')
                for source in artifact['sources']:
                    if source['source_key']=='19x19':native.add(numeric(source['source_item_id']))
    require(not ids&native,'applied native receipt overlap with isolation IDs')
    pending=[];skipped=0;resumed=0
    # Validate every target row before the first remember_item; never overwrite foreign state.
    for record in records:
        row=existing.get(record['source_item_id']);meta=provenance(record)
        error='A reviewed isolation: '+','.join(record['reason_codes'])
        require(len(error)<=512,'isolation error exceeds journal limit')
        if row:
            clean=all(row[name] is None for name in EMPTY_FIELDS) and row['source_metadata']==meta and row['next_retry_at'] is None
            discovered=row['status']=='discovered' and row['resume_phase'] is None and row['attempts']==0 and row['error'] is None
            quarantined=row['status']=='quarantined' and row['resume_phase']=='discovered' and row['attempts']==1 and row['error']==error
            require(clean and (discovered or quarantined),'existing row conflicts with reviewed report')
            if quarantined:skipped+=1;continue
            resumed+=1
        pending.append((record['source_item_id'],meta,error))
    result={'apply':apply,'report_sha256':REPORT_SHA,'isolations':257,'planned_new':len(pending)-resumed,'planned_resume':resumed,'created':0,'resumed':0,'skipped':skipped,'quarantined':0}
    if apply:
        store=StateStore(engine)
        for external_id,meta,error in pending:
            store.remember_item('19x19',external_id,source_metadata=meta)
            store.advance_item('19x19',external_id,'quarantined',expected_status='discovered',error=error)
            result['quarantined']+=1
        result.update(created=len(pending)-resumed,resumed=resumed)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path,default=Path('/tmp/A-isolation-report.json'))
    args=parser.parse_args()
    from katrain.cron import config
    from katrain.cron.db import engine
    from katrain.cron.jobs.kifu_ingest import _session_lock
    require(not config.KIFU_INGEST_ENABLED and not config.KIFU_INGEST_LLM_ENABLED and config.KIFU_INGEST_MAX_TOKENS==0,'B scheduling/LLM must be disabled with cap zero')
    with _session_lock(engine) as acquired:
        require(acquired,'another B run holds the session lock')
        print(json.dumps(operate(engine,Path(config.KIFU_INGEST_STAGING_DIR),args.report,apply=args.apply),sort_keys=True))

if __name__=='__main__':
    try:main()
    except SafetyError as exc:print('STOP: '+str(exc),file=sys.stderr);sys.exit(2)
    except Exception as exc:print('STOP: '+type(exc).__name__+' (details suppressed)',file=sys.stderr);sys.exit(3)
