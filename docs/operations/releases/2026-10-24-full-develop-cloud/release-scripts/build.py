import pathlib,json,subprocess,hashlib,os,sys,tarfile
r=pathlib.Path(sys.argv[1]);name=sys.argv[2];sha='495d0284c05cb7c9e8b388ded49a82f2959bfdf7'
c=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
(r/'rollback').mkdir(exist_ok=True,mode=0o700);(r/'rollback/container.private.json').write_text(json.dumps(c));os.chmod(r/'rollback/container.private.json',0o600)
configfiles=c['Config']['Labels']['com.docker.compose.project.config_files'].split(',');project=c['Config']['Labels']['com.docker.compose.project'];compose=['docker','compose','-p',project]+sum((['-f',p] for p in configfiles),[])
original=json.loads(subprocess.check_output(compose+['config','--format','json']));(r/'rollback/compose.private.json').write_text(json.dumps(original));os.chmod(r/'rollback/compose.private.json',0o600)
base=c['Config']['Image'];assert subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',base],text=True).strip()==c['Image']
context=r/'context';context.mkdir(exist_ok=True);source=context/'source';source.mkdir(exist_ok=True)
with tarfile.open(r/'app-495d0284c.tar.gz','r:gz') as t:t.extractall(source)
for p in json.loads((r/'static-delete.json').read_text()):
 (source/p).unlink(missing_ok=True)
with tarfile.open(r/'frontend-delta.tar.gz','r:gz') as t:t.extractall(source)
with tarfile.open(r/'locales-fixed.tar.gz','r:gz') as t:t.extractall(source)
manifest=json.loads((r/'final-source-manifest.json').read_text())
for p,d in manifest['files'].items():
 f=source/p;data=os.readlink(f).encode() if f.is_symlink() else f.read_bytes();assert hashlib.sha256(data).hexdigest()==d,p
shutil=__import__('shutil');shutil.copy2(r/'final-source-manifest.json',source/'.full-develop-source-manifest.json')
user=c['Config'].get('User') or 'root'
(context/'Dockerfile').write_text(f'''FROM {base}
USER root
WORKDIR /
RUN rm -rf /app
COPY --chown=10001:10001 source/ /app/
ENV KATRAIN_BUILD_SHA={sha} KATRAIN_FRONTEND_BUILD_SHA={sha}
LABEL org.opencontainers.image.revision="{sha}" io.smartbox.release.scope="complete pinned application source and full/admin frontend; inherited dependency layer only"
WORKDIR /app
USER {user}
''')
tag='katrain-full-develop:495d0284c-20261024'
with (r/'build.log').open('w') as log:subprocess.run(['docker','build','--pull=false','-t',tag,str(context)],stdout=log,stderr=subprocess.STDOUT,check=True)
image=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',tag],text=True).strip()
verify="import pathlib,json,hashlib,os; root=pathlib.Path('/app'); m=json.loads((root/'.full-develop-source-manifest.json').read_text()); wrong=[]; [wrong.append(p) for p,h in m['files'].items() if hashlib.sha256(os.readlink(root/p).encode() if (root/p).is_symlink() else (root/p).read_bytes()).hexdigest()!=h]; assert not wrong,wrong; import katrain.web.server; print('VERIFIED',len(m['files']),'files; server import ok')"
probe=subprocess.check_output(['docker','run','--rm','--network','none','-e','KATRAIN_DATABASE_URL=sqlite:///:memory:','-e','KATRAIN_MODE=server','--entrypoint','python3',tag,'-c',verify],text=True)
meta={'revision':sha,'image':image,'tag':tag,'base_dependency_image':c['Image'],'original_container_id':c['Id'],'original_started_at':c['State']['StartedAt'],'source_manifest_sha256':hashlib.sha256((r/'final-source-manifest.json').read_bytes()).hexdigest(),'source_file_count':len(manifest['files']),'source_and_frontend_probe':probe.strip(),'compose_files':configfiles,'project':project,'runtime_user':user}
(r/'built.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
