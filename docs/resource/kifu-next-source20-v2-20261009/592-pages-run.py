import json,re,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parent;env,phase=sys.argv[1:]
assert env in {'PROD','TEST'} and phase in {'preview','apply','verify'}
web='katrain-web'if env=='TEST'else'katrain-ucloud-katrain-web-1'
image={'TEST':'sha256:61ffcb3f86e9733b63eb7b25c2e34005e651e5ab1da4e7ad353d64f5815df1f1','PROD':'sha256:6ffe9b6dad44ae280dc756d8468f1695337ca786541976413b515e614ebab3c5'}[env]
assert subprocess.check_output(['docker','image','inspect',image,'--format','{{.Id}}'],text=True).strip()==image
meta=json.loads(subprocess.check_output(['docker','inspect',web],text=True))[0]
url=next(e.split('=',1)[1]for e in meta['Config']['Env']if e.startswith('KATRAIN_DATABASE_URL='))
args=['docker','run','--rm','--read-only','--network','container:'+web,'-e','KATRAIN_DATABASE_URL='+url,'-v',str(p)+':/work:ro','-v',str(p/'player_pages.py')+':/app/katrain/web/kifu/player_pages.py:ro','--entrypoint','python',image,'/work/592-pages-inner.py',env,phase]
r=subprocess.run(args,capture_output=True,text=True)
if r.returncode:print(re.sub(r'\w+://\S+', '[redacted URL]', r.stderr));raise SystemExit(r.returncode)
d=json.loads(r.stdout);receipt=p/f'{env}-pages-{phase}.json'
assert not receipt.exists(),f'refusing to overwrite {receipt}'
receipt.write_text(r.stdout)
report=d.get('report',d.get('preview',{}))
print(json.dumps({'environment':env,'phase':phase,'passed':True,'players_scanned':report.get('players_scanned'),'pages_added':report.get('pages_added'),'players_changed':report.get('players_changed')}))
