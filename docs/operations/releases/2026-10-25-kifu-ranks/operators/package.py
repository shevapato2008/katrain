from pathlib import Path
import subprocess,tarfile,hashlib,json,shutil,sys,io
root=Path('/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/kifu-rank-fallback-20261025')
stage=Path('/private/tmp/kifu-rank-fallback-rk-20261025');payload=stage/'payload'
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
parent=sys.argv[1]
assert subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)==''
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/develop'],cwd=root,text=True).split()[0]==source
files=[p for p in subprocess.check_output(['git','ls-tree','-r','--name-only',source,'katrain'],cwd=root,text=True).splitlines() if p.endswith('.py') and not p.startswith('katrain/vision/tools/')]
assert not payload.exists();(payload/'runtime').mkdir(parents=True)
files += ['katrain/web/content/kiosk19_policy.json']
assert all(not str(p).startswith('._') for p in files)
archive=subprocess.check_output(['git','archive',source,*files],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(payload/'runtime')
for name in ['static','static-kiosk-2d']:
 source_dir=root/'katrain/web'/name
 assert (source_dir/'index.html').exists()
 shutil.copytree(source_dir,payload/name)
manifest={'release':'20261025-kifu-rank-fallback-'+source[:9],'katrain_source':source,'smartbox_parent':parent,'scope':'tracked runtime Python excluding vision/tools plus versioned content policy JSON; complete full and strict static built from published develop; preserve device configuration, state, models and other games','files':{}}
for file in sorted(payload.rglob('*')):
 if file.is_file():manifest['files'][str(file.relative_to(payload))]=hashlib.sha256(file.read_bytes()).hexdigest()
(payload/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(stage/'payload.tar.gz','w:gz') as tar:
 for item in sorted(payload.iterdir()):tar.add(item,arcname=item.name)
h=hashlib.sha256((stage/'payload.tar.gz').read_bytes()).hexdigest()
(stage/'payload.tar.gz.sha256').write_text(h+'  payload.tar.gz\n')
print(json.dumps({'source':source,'parent':parent,'runtime_python_count':sum(p.endswith('.py') for p in files),'manifest_files':len(manifest['files']),'archive_sha256':h,'archive_bytes':(stage/'payload.tar.gz').stat().st_size}))
