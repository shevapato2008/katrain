"""Capture post-590/page mixed20 context from the currently running web containers.

Run only after root confirms both services load the reviewed orthographic module
and the batch-590 page synchronization is complete. This never touches the
approved actual-source files or changes SQL data.
"""

import gzip
import json
import shlex
import subprocess
from pathlib import Path


D = Path(__file__).parent
HOSTS = {
    "PROD": ("ucloud-v100", "katrain-ucloud-katrain-web-1"),
    "TEST": ("home-ubuntu", "katrain-web"),
}
PROD_IDS = (4771, 5397, 5297, 6599, 6626, 4235, 6629, 6686, 6259,
            600, 229, 595, 385, 662, 320, 446, 391, 5396, 4276, 4782)

REMOTE = r'''
import datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from sqlalchemy import text
from katrain.web.core.models_db import KifuPlayer,KifuPlayerName,KifuNameResearchEvidence,KifuNameBatch,KifuNameSourceRegistry
from katrain.web.kifu.name_batch import catalog_snapshot_sha,approved_name_snapshot,orthographic_alias_snapshot
from katrain.web.kifu.name_inventory import build_inventory
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
inventory=build_inventory(engine)
catalog=catalog_snapshot_sha(engine)
approved=approved_name_snapshot(engine)
rows=[]
with engine.connect() as conn:
 conn.exec_driver_sql('SET TRANSACTION READ ONLY')
 conn.exec_driver_sql("SET LOCAL statement_timeout='90s'")
 aliases=orthographic_alias_snapshot(conn)
 registry=dict(conn.execute(select(KifuNameSourceRegistry.__table__).order_by(KifuNameSourceRegistry.id.desc()).limit(1)).mappings().one())
 batch=dict(conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id==590)).mappings().one())
 assert batch['status']=='applied'
 if ENV=='PROD':
  players=conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.id.in_(TARGETS))).mappings().all()
  bytarget={p['id']:dict(p) for p in players}
 else:
  players=conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.canonical_name.in_(list(TARGETS.values())))).mappings().all()
  assert len(players)==len(TARGETS)
  byname={p['canonical_name']:dict(p) for p in players}
  bytarget={prod_id:byname[canonical] for prod_id,canonical in TARGETS.items()}
 assert len(bytarget)==20 and len({p['id']for p in bytarget.values()})==20
 ids=[p['id']for p in bytarget.values()]
 with Session(bind=conn)as session:
  q=_approved_names(session,KifuPlayerName,'player_id').filter(KifuPlayerName.player_id.in_(ids))
  qualified=_qualified_name_rows(session,q,KifuPlayerName,'player_id')
  qualified_keys={(n.player_id,n.lang,n.display_name)for n,e in qualified}
 for prod_id in PROD_IDS:
  player=bytarget[prod_id];pid=player['id']
  names=[dict(n)for n in conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==pid)).mappings()]
  bylang={n['lang']:n for n in names}
  assert len(bylang)==len(names)
  target_lang='ko'if prod_id in (5396,4276,4782)else'tw'
  target=bylang.get(target_lang)
  evidence=(dict(conn.execute(select(KifuNameResearchEvidence.__table__).where(
      KifuNameResearchEvidence.id==target['evidence_id'])).mappings().one())
      if target is not None and target['evidence_id'] is not None else None)
  if prod_id in (5396,4276,4782):
   assert {'cn','tw','jp','en'}<={lang for owner,lang,name in qualified_keys if owner==pid}
   assert not any(owner==pid and lang=='ko'for owner,lang,name in qualified_keys)
  else:
   source_lang='jp'if prod_id in (4771,5397,5297,6599,6626,4235,6629,6686,6259)else'cn'
   assert any(owner==pid and lang==source_lang for owner,lang,name in qualified_keys)
   assert not any(owner==pid and lang=='tw'for owner,lang,name in qualified_keys)
  games=[dict(game)for game in conn.execute(text('SELECT id,black_player_id,white_player_id,date_played,player_black,player_white,black_rank,white_rank,result,sgf_content FROM kifu_albums WHERE black_player_id=:id OR white_player_id=:id ORDER BY id'),{'id':pid}).mappings()]
  for game in games:
   game['sgf_utf8_sha256']=hashlib.sha256(game.pop('sgf_content').encode()).hexdigest()
   game['side']='black'if game['black_player_id']==pid else'white'
  rows.append({'prod_id':prod_id,'id':pid,'owner_preimage':player,
               'canonical_name':player['canonical_name'],'current_names':names,
               'target_lang':target_lang,'target_name_preimage':target,
               'target_evidence_preimage':evidence,
               'qualified_languages':sorted({lang for owner,lang,name in qualified_keys if owner==pid}),
               'linked_album_members':games,'game_slots':len(games)})
 conn.rollback()
code={name:hashlib.sha256(Path('/app/katrain/web/kifu',name).read_bytes()).hexdigest()
      for name in ('identity.py','name_candidates.py','name_evidence.py','name_orthographic.py','name_batch.py','name_inventory.py')}
result={'environment':ENV,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'read_only':True,'inventory':inventory,'catalog_sha256':catalog,
        'approved_name_snapshot':approved,'known_aliases':aliases,'source_registry':registry,
        'batch590':{'id':590,'status':batch['status'],'bundle_sha256':batch['bundle_sha256'],'applied_at':batch['applied_at']},
        'code_sha256':code,'image_id':IMAGE,'rows':rows,
        'game_slots':sum(row['game_slots']for row in rows),
        'unique_albums':len({game['id']for row in rows for game in row['linked_album_members']})}
sys.stdout.buffer.write(gzip.compress(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),
                                            default=lambda x:x.isoformat()if isinstance(x,datetime.datetime)else str(x)).encode(),mtime=0))
engine.dispose()
'''


def capture(environment, targets, image):
    host, container = HOSTS[environment]
    program = (f"ENV={environment!r}\nTARGETS={targets!r}\nIMAGE={image!r}\n"
               f"PROD_IDS={PROD_IDS!r}\n" + REMOTE)
    command = (
        f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
        ' | grep "^KATRAIN_DATABASE_URL="'
        f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
        f' --entrypoint python {shlex.quote(image)} -c {shlex.quote(program)}'
    )
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command],
                            capture_output=True)
    if result.returncode:
        import re
        message = re.sub(r"\w+://\S+", "[redacted URL]", result.stderr.decode(errors="replace")[-1800:])
        raise RuntimeError(f"{environment}: {message}")
    data = json.loads(gzip.decompress(result.stdout))
    assert data["environment"] == environment and len(data["rows"]) == 20
    path = D / f"{environment}-mixed20-fresh-post590-pages.json.gz"
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes(result.stdout)
    print(environment, "captured 20 fresh owners; inventory", data["inventory"]["sha256"], flush=True)
    return data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-confirms-deployed-and-pages-synced", action="store_true")
    parser.add_argument("--prod-image", required=True, help="current pinned native r3 importer image ID")
    parser.add_argument("--test-image", required=True, help="current pinned native r3 importer image ID")
    args = parser.parse_args()
    if not args.root_confirms_deployed_and_pages_synced:
        raise SystemExit("root deployment/page-sync confirmation required")
    prod = capture("PROD", list(PROD_IDS), args.prod_image)
    canonical_by_prod = {row["prod_id"]: row["canonical_name"] for row in prod["rows"]}
    capture("TEST", canonical_by_prod, args.test_image)
