from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json,sys,tempfile,shutil
from datetime import datetime,timezone
from sqlalchemy import select,func
sys.path.insert(0,'/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024')
from tests.web_ui.test_kifu_incremental_catalog import make_engine,manifest,decision,publish,assert_qualified
from katrain.web.core.models_db import KifuAlbum,KifuNameBatch,KifuRawEventName
from katrain.web.kifu.name_candidates import canonical_sha256
source=Path('/tmp/golaxy-event-correction-20261024.py').read_text();ns={};exec(compile(source[:source.index('parser=argparse.ArgumentParser()')],'correction-helper','exec'),ns)
with tempfile.TemporaryDirectory(prefix='golaxy-correction-sqlite-') as tmp:
 root=Path(tmp);engine=make_engine(root/'fixture.db');ns['engine']=engine
 value={'format':'kifu-incremental-manifest-v1','publication_key':'fixture-six-event-corrections','games':[],'decisions':[]}
 for raw in dict.fromkeys(c['raw'] for c in ns['SPEC']['cells']):
  cells=[c for c in ns['SPEC']['cells'] if c['raw']==raw];ids=cells[0]['sources'];members=[]
  for sid in ids:
   m=manifest(sid,event=raw);game=m['games'][0];game['origin_path']=f'data/kifu-album/19x19/{sid}.sgf';game['sgf_content']=game['sgf_content'].replace('whole original','fixture '+sid);digest=sha256(game['sgf_content'].encode()).hexdigest();game['raw_sha256']=game['sgf_sha256']=digest;value['games'].append(game)
   members.append({'source_key':'19x19','source_item_id':sid,'slot':'event','sgf_sha256':digest})
  d=decision({'games':[value['games'][-1]]},'raw_event',raw);d['source_items']=members
  d['displays']={lang:raw for lang in ['cn','tw','jp','ko','en']}
  d['displays']['en']='Fixture event '+raw
  for cell in cells:d['displays'][cell['lang']]=cell['old']
  d['methods']={lang:'translation' for lang in d['displays']};d['methods']['cn']='retain_original'
  from katrain.kifu_ingest.catalog import review_content_sha256
  d['review']['content_sha256']=review_content_sha256(d);value['decisions'].append(d)
 receipt=publish(engine,value);ids=[g['album_id'] for g in receipt['games']];assert len(set(ids))==6
 with engine.connect() as c:
  before=[tuple(r) for r in c.execute(select(KifuAlbum.id,KifuAlbum.sgf_content,KifuAlbum.source_path,KifuAlbum.player_black,KifuAlbum.player_white,KifuAlbum.event,KifuAlbum.date_played).order_by(KifuAlbum.id))]
  native=c.execute(select(KifuNameBatch.id,KifuNameBatch.reviewed_artifact).where(KifuNameBatch.bundle_sha256==canonical_sha256(value))).one();original_native_sha=canonical_sha256(native.reviewed_artifact)
 artifacts=root/'artifacts';artifacts.mkdir();shutil.copy('/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/golaxy-hourly-release-20261024/docs/resource/kifu-name-source-registry.json',artifacts/'registry-input.json')
 prepared=ns['prepare'](artifacts,'TEST')
 capture=json.loads((artifacts/'capture.json').read_text())
 approval={'decision':'approved','reviewer_id':ns['REVIEWER'],'spec_sha256':capture['spec_sha256'],'capture_sha256':canonical_sha256(capture),'reviewed_at':datetime.now(timezone.utc).isoformat(),'note':'Synthetic isolated SQLite test approval only; never a production approval.'}
 ns['write'](artifacts/'independent-approval.json',approval);finalized=ns['finalize'](artifacts)
 preview=ns['validate_or_apply'](artifacts,False);assert preview['ready'] and preview['write_ready']
 ns['write'](artifacts/'bundle-apply-approval.json',{'decision':'approved','reviewer_id':ns['REVIEWER'],'bundle_sha256':finalized['bundle_sha256'],'spec_sha256':capture['spec_sha256'],'target':'TEST','note':'Synthetic fixture approval only.'})
 applied=ns['validate_or_apply'](artifacts,True);assert applied['status']=='applied'
 replay=ns['validate_or_apply'](artifacts,True);assert replay['status']=='already_applied' and replay['change_count']==0
 with engine.connect() as c:
  after=[tuple(r) for r in c.execute(select(KifuAlbum.id,KifuAlbum.sgf_content,KifuAlbum.source_path,KifuAlbum.player_black,KifuAlbum.player_white,KifuAlbum.event,KifuAlbum.date_played).order_by(KifuAlbum.id))];assert after==before
  assert canonical_sha256(c.scalar(select(KifuNameBatch.reviewed_artifact).where(KifuNameBatch.id==native.id)))==original_native_sha
 assert_qualified(engine,ids)
 print(json.dumps({'isolated_sqlite':'passed','games_unchanged':len(ids),'corrected_cells':len(ns['SPEC']['cells']),'native_apply':applied,'native_replay':replay,'all_five_languages_qualified':True},indent=2))
 engine.dispose()
