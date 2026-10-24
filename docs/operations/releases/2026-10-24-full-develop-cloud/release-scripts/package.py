import subprocess,hashlib,pathlib,tarfile,json,fnmatch,os
wt=pathlib.Path('/Users/fan/.config/superpowers/worktrees/katrain-kiosk-debug/full-develop-cloud-20261024');out=pathlib.Path('/private/tmp/full-develop-cloud-20261024');source='495d0284c05cb7c9e8b388ded49a82f2959bfdf7';manifest={};included=[]
rows=subprocess.check_output(['git','ls-tree','-rz','--full-tree',source],cwd=wt).split(b'\0')
for row in rows:
 if not row:continue
 meta,rawpath=row.split(b'\t',1);mode,kind,oid=meta.decode().split();p=rawpath.decode()
 if kind!='blob':continue
 if p.startswith(('superpowers/','tmp/','.firecrawl/','runs/','data/go4_')) or p.startswith('docs/resource/') and p not in ['docs/resource/kifu-name-source-registry.json','docs/resource/kifu-name-seed.json'] or '/' not in p and fnmatch.fnmatch(p,'yolo*.pt'):continue
 path=wt/p;data=os.readlink(path).encode() if mode=='120000' else path.read_bytes();assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==oid,p
 manifest[p]=hashlib.sha256(data).hexdigest();included.append(p)
for directory in ['katrain/web/static','katrain/web/static-admin']:
 for path in (wt/directory).rglob('*'):
  if path.is_file():p=str(path.relative_to(wt));manifest[p]=hashlib.sha256(path.read_bytes()).hexdigest();included.append(p)
for path in (wt/'katrain/i18n/locales').glob('*/LC_MESSAGES/katrain.mo'):
 p=str(path.relative_to(wt));manifest[p]=hashlib.sha256(path.read_bytes()).hexdigest();included.append(p)
included=sorted(set(included));(out/'source-manifest.json').write_text(json.dumps({'revision':source,'files':manifest},indent=2)+'\n')
with tarfile.open(out/'app-495d0284c.tar.gz','w:gz',compresslevel=1) as tar:
 for p in included:tar.add(wt/p,arcname=p,recursive=False)
print(len(included),'complete app/build source and compiled files',sum((wt/p).stat().st_size for p in included)//1024//1024,'MiB inputs; archive',(out/'app-495d0284c.tar.gz').stat().st_size//1024//1024,'MiB')
(out/'source-495d0284c.tar.gz').unlink()
