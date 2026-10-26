"""LOCAL ONLY: package committed runtime files and already-built full/strict UI."""
import argparse, hashlib, io, json, pathlib, re, subprocess, tarfile

RUNTIME = [
    'katrain/cron/migrations/004_kifu_player_ranks.sql',
    'katrain/kifu_ingest/catalog.py', 'katrain/kifu_ingest/orchestration.py',
    'katrain/kifu_ingest/ranks.py', 'katrain/kifu_ingest/staging.py',
    'katrain/kifu_ingest/sync.py', 'katrain/kifu_ingest/verification.py',
    'katrain/web/api/v1/endpoints/kifu.py', 'katrain/web/core/auth.py',
    'katrain/web/core/migrations.py', 'katrain/web/core/models_db.py',
    'katrain/web/kifu/name_batch.py', 'katrain/web/kifu/player_ranks.py',
    'scripts/kifu_rank_correction.py',
]
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True); p.add_argument('--sha', required=True)
    p.add_argument('--full'); p.add_argument('--strict'); p.add_argument('--ui-provenance')
    p.add_argument('--backend-only',action='store_true'); p.add_argument('--inherited-ui-source-sha')
    p.add_argument('--output', required=True)
    a=p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', a.sha): raise ValueError('full_published_sha_required')
    if a.backend_only:
        if any([a.full,a.strict,a.ui_provenance]) or not a.inherited_ui_source_sha or not re.fullmatch('[0-9a-f]{40}',a.inherited_ui_source_sha): raise ValueError('backend_only_requires_inherited_ui_sha_and_no_ui_artifacts')
    elif not all([a.full,a.strict,a.ui_provenance]): raise ValueError('full_ui_artifacts_and_provenance_required')
    def git(*args): return subprocess.check_output(['git','-C',a.repo,*args],stderr=subprocess.DEVNULL)
    if git('rev-parse',a.sha+'^{commit}').decode().strip()!=a.sha: raise ValueError('commit_not_exact')
    data={x:git('show',a.sha+':'+x) for x in RUNTIME}
    static={}
    provenance={}
    if not a.backend_only:
        # Existing full-UI path remains available, but this backend-only release never uses it.
        provenance=json.loads(pathlib.Path(a.ui_provenance).read_text())
        if provenance.get('source_develop_sha')!=a.sha: raise ValueError('ui_source_sha_mismatch')
        for root, path in [('katrain/web/static',a.full),('katrain/web/static-kiosk-2d',a.strict)]:
            directory=pathlib.Path(path)
            if not (directory/'index.html').is_file(): raise ValueError('missing_built_index')
            for f in sorted(directory.rglob('*')):
                if f.is_symlink(): raise ValueError('asset_symlink')
                if f.is_file(): static[root+'/'+str(f.relative_to(directory))]=f.read_bytes()
        if provenance.get('static_files_sha256')!={x:sha(b) for x,b in static.items()}: raise ValueError('ui_artifact_hash_manifest_mismatch')
    manifest={'source_develop_sha':a.sha,'runtime_files_sha256':{x:sha(b) for x,b in data.items()},
              'static_files_sha256':{x:sha(b) for x,b in static.items()},
              'deployment_scope':'backend-only' if a.backend_only else 'runtime-and-ui'}
    if a.backend_only: manifest.update({'ui_mode':'inherited_unchanged','inherited_ui_source_sha':a.inherited_ui_source_sha})
    else: manifest['ui_provenance_sha256']=sha(pathlib.Path(a.ui_provenance).read_bytes())
    out=pathlib.Path(a.output); out.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    with tarfile.open(out/'overlay.tar','w') as t:
        for name,b in {**data,**static,'manifest.json':raw}.items():
            info=tarfile.TarInfo(name); info.size=len(b); info.mode=0o644
            t.addfile(info,io.BytesIO(b))
    (out/'manifest.json').write_bytes(raw)
    print(json.dumps({'bundle':str(out/'overlay.tar'),'bundle_sha256':sha((out/'overlay.tar').read_bytes()),
                      'manifest_sha256':sha(raw),'runtime_count':len(data),'static_count':len(static),
                      'source_develop_sha':a.sha,'remote_executed':False},indent=2))
if __name__=='__main__': main()
