"""Capture exact conventional JP rows and creation journals with the pinned JP importer."""

import gzip
import json
import shlex
import subprocess
from pathlib import Path

DIRECTORY = Path(__file__).parent
HOSTS = {
    "PROD": ("ucloud-v100", "katrain-ucloud-katrain-web-1",
             "sha256:16ff2a118049c852d674800d9b0c8e4a676a68e10aca8d8baf67f30f64cd0a0c"),
    "TEST": ("home-ubuntu", "katrain-web",
             "sha256:52907d65efc9e59b8b546d2e335d5d45729aa0eed1c5e1480be7f4cbe0d28259"),
}
REMOTE = r'''
import datetime,gzip,hashlib,json,os,sys,unicodedata
from pathlib import Path
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session
from katrain.web.core.models_db import KifuPlayer,KifuPlayerName,KifuNameResearchEvidence,KifuNameBatch,KifuNameChange
from katrain.web.kifu.name_batch import _image
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_orthographic import verified_source_live
from katrain.web.kifu.identity import _approved_names,_qualified_name_rows
def encode(value):
    return value.isoformat() if isinstance(value,datetime.datetime) else str(value)
expected={"katrain/web/kifu/identity.py":"932d36940b2ddd3a90c4cbfc38802daf4ecb6255d1678fe1a8f3d2e3d457b127",
"katrain/web/kifu/name_evidence.py":"7f841117402635a7cfd3044c177f7591315f7175f917095b2adadb89ffdf1a42",
"katrain/web/kifu/name_orthographic.py":"346727568e58437dba72d6946ac9e3de98e929fbbca25a75d15223a231c5938e",
"katrain/web/kifu/name_batch.py":"cd91d45b1671ea10924661880094980e21e6d170efba03c83036ef5c03b94a00"}
assert all(hashlib.sha256(Path('/app',f).read_bytes()).hexdigest()==h for f,h in expected.items())
engine=create_engine(os.environ['KATRAIN_DATABASE_URL'],connect_args={'options':'-c default_transaction_read_only=on'})
rows=[]
with engine.connect() as conn:
    conn.exec_driver_sql('SET TRANSACTION READ ONLY')
    conn.exec_driver_sql("SET LOCAL statement_timeout='30s'")
    with Session(bind=conn) as session:
        query=_approved_names(session,KifuPlayerName,'player_id').filter(
            ((KifuPlayerName.lang=='jp') & KifuPlayerName.display_name.in_(TARGET_NAMES)) |
            ((KifuPlayerName.lang=='cn') & (KifuPlayerName.display_name=='安东阳向')))
        qualified=_qualified_name_rows(session,query,KifuPlayerName,'player_id')
        assert len(qualified)==len(TARGET_NAMES)+1
        assert len({n.display_name for n,e in qualified})==len(TARGET_NAMES)+1
        for n,e in qualified:
            assert n.decision_kind==e.decision_kind=='conventional'
            original=n.display_name
            assert 2<=len(original)<=16 and all(unicodedata.name(c,'').startswith('CJK UNIFIED IDEOGRAPH') for c in original)
            owner={'kind':'player','id':n.player_id}
            name,evidence=_image(conn,KifuPlayerName.__table__,n.id),_image(conn,KifuNameResearchEvidence.__table__,e.id)
            changes=conn.execute(select(KifuNameChange.__table__).where(KifuNameChange.target_table=='kifu_name_research_evidence',KifuNameChange.target_row_id==e.id)).mappings().all()
            changes=[change for change in changes if change['before_image'] is None]
            assert len(changes)==1
            batch=conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id==changes[0]['batch_id'])).mappings().one()
            source_batch={'id':batch['id'],'bundle_sha256':batch['bundle_sha256'],'evidence_creation_sha256':registry_sha256(evidence)}
            reference='verified_japanese_display' if n.lang=='jp' else 'verified_chinese_display'
            target_language='cn' if n.lang=='jp' else 'tw'
            target_display=original if n.lang=='jp' else '安東陽向'
            content={'reference_kind':reference,'owner':owner,'original_name':original,'source_lang':'ja' if n.lang=='jp' else 'zh-Hans','source_script':'Kanji' if n.lang=='jp' else 'Hans','binding':{'kind':reference,'owner':owner,'source_name':name,'source_evidence':evidence,'source_batch':source_batch}}
            assert verified_source_live(conn,{'content':content}) is True
            current_target=conn.execute(select(KifuPlayerName.__table__).where(KifuPlayerName.player_id==n.player_id,KifuPlayerName.lang==target_language)).mappings().one_or_none()
            assert current_target is None
            player=conn.execute(select(KifuPlayer.__table__).where(KifuPlayer.id==n.player_id)).mappings().one()
            journal=conn.execute(select(KifuNameChange.__table__).where(KifuNameChange.batch_id==batch['id'],KifuNameChange.target_row_id.in_([n.id,e.id]),KifuNameChange.target_table.in_(['kifu_player_names','kifu_name_research_evidence']))).mappings().all()
            games=conn.execute(text('SELECT id,black_player_id,white_player_id,date_played,player_black,player_white,black_rank,white_rank,result,sgf_content FROM kifu_albums WHERE black_player_id=:id OR white_player_id=:id ORDER BY id'),{'id':n.player_id}).mappings().all()
            games=[dict(game) for game in games]
            for game in games:
                game['sgf_utf8_sha256']=hashlib.sha256(game.pop('sgf_content').encode('utf-8')).hexdigest()
                game['side']='black' if game['black_player_id']==n.player_id else 'white'
            rows.append({'id':n.player_id,'canonical_name':player['canonical_name'],'owner_preimage':dict(player),'source_name':name,'source_evidence':evidence,'source_batch':source_batch,'source_batch_status':batch['status'],'source_creation_journal':[dict(j) for j in journal],'target_language':target_language,'target_display':target_display,'current_target':None,'games':len(games),'linked_album_members':[dict(g) for g in games],'unsigned_anchor_content':content,'source_qualified_product_gate':True,'verified_source_live_new_JP_branch':True})
    conn.rollback()
out={'environment':ENVIRONMENT,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image_id':IMAGE_ID,'verified_importer_files':expected,'read_only_database_connections':True,'rows':sorted(rows,key=lambda r:r['id'])}
sys.stdout.buffer.write(gzip.compress(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=encode).encode(),mtime=0))
engine.dispose()
'''


def capture(environment, names):
    host, container, image = HOSTS[environment]
    program = ('TARGET_NAMES=' + repr(names) + '\nENVIRONMENT=' + repr(environment)
               + '\nIMAGE_ID=' + repr(image) + '\n' + REMOTE)
    command = (
        f'docker inspect --format "{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}" {container}'
        ' | grep "^KATRAIN_DATABASE_URL="'
        f' | docker run --rm --read-only -i --env-file /dev/stdin --network container:{container}'
        f' --entrypoint python {image} -c {shlex.quote(program)}'
    )
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host, command],
                            capture_output=True)
    if result.returncode:
        import re
        diagnostic = result.stderr.decode('utf-8', errors='replace').splitlines()[-4:]
        diagnostic = [re.sub(r'\w+://\S+', '[redacted URL]', line) for line in diagnostic]
        raise RuntimeError(environment + ': ' + '\n'.join(diagnostic))
    captured = json.loads(gzip.decompress(result.stdout))
    assert len(captured['rows']) == len(names)+1 == 20
    (DIRECTORY / f'{environment}-jp-source-readonly.json').write_text(
        json.dumps(captured, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    print(environment, len(captured['rows']), 'qualified conventional JP/CN NULL',
          'games', sum(r['games'] for r in captured['rows']), 'new JP live source gate PASS')


if __name__ == '__main__':
    candidates = json.loads((DIRECTORY / 'live-PROD-candidates.json').read_text())
    for environment in HOSTS:
        capture(environment, [row['display_name'] for row in candidates])
