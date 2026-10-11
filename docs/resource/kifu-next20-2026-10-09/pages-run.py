import json,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parent;env,phase=sys.argv[1:]
web='katrain-web'if env=='TEST'else'katrain-ucloud-katrain-web-1'
image={'TEST':'sha256:62283df0e9c81b3367e7865acaa8015a9d4931be9f162b6ec969e80c9073d845','PROD':'sha256:ed6112e7006cad941c52ab28f668af0235ddad2d9761128eeee745c63625c67e'}[env]
meta=json.loads(subprocess.check_output(['docker','inspect',web],text=True))[0]
url=next(e.split('=',1)[1]for e in meta['Config']['Env']if e.startswith('KATRAIN_DATABASE_URL='))
args=['docker','run','--rm','--read-only','--network','container:'+web,'-e','KATRAIN_DATABASE_URL='+url,'-v',str(p)+':/work:ro','-v',str(p/'player_pages.py')+':/app/katrain/web/kifu/player_pages.py:ro','--entrypoint','python',image,'/work/pages-inner.py',env,phase]
r=subprocess.run(args,capture_output=True,text=True)
if r.returncode:print(r.stderr);raise SystemExit(r.returncode)
d=json.loads(r.stdout);(p/f'{env}-pages-{phase}.json').write_text(r.stdout)
report=d.get('report',d.get('preview',{}))
print(json.dumps({'environment':env,'phase':phase,'passed':True,'players_scanned':report.get('players_scanned'),'pages_added':report.get('pages_added'),'players_changed':report.get('players_changed')}))
