"""Read-only /app hashes; also reused in offline candidate containers."""
import hashlib, importlib, json, pathlib, re, runpy, sys

PROTECTED = [
 'katrain/web/server.py','katrain/web/core/pvp_territory.py','scripts/kifu_incremental.py',
 'katrain/cron/config.py','katrain/cron/jobs/kifu_ingest.py','katrain/cron/scheduler.py',
 'katrain/cron/db.py','katrain/cron/models.py','katrain/cron/__main__.py',
 'katrain/kifu_ingest/__init__.py','katrain/kifu_ingest/catalog.py',
 'katrain/kifu_ingest/exclusions.py','katrain/kifu_ingest/inventory.py',
 'katrain/kifu_ingest/maintenance.py','katrain/kifu_ingest/name_reuse.py',
 'katrain/kifu_ingest/names.py','katrain/kifu_ingest/orchestration.py',
 'katrain/kifu_ingest/preparation.py','katrain/kifu_ingest/recent.py',
 'katrain/kifu_ingest/source_19x19.py','katrain/kifu_ingest/staging.py',
 'katrain/kifu_ingest/state.py','katrain/kifu_ingest/sync.py',
 'katrain/kifu_ingest/verification.py','katrain/web/kifu/library.py',
 'katrain/web/kifu/name_parse.py','katrain/web/kifu/identity.py',
 'katrain/core/sgf_parser.py','katrain/web/core/db.py','katrain/web/core/config.py',
]
ROOTS=['katrain/web/static','katrain/web/static-kiosk-2d']
def sha(b): return hashlib.sha256(b).hexdigest()
def probe(extra=(), imports=False,kind='web'):
 root=pathlib.Path('/app'); paths=sorted(set(PROTECTED)|set(extra))
 out={'source_files':{p:sha((root/p).read_bytes()) if (root/p).is_file() else None for p in paths},
      'static_files':{},'active_static_graph':{}}
 for name in ROOTS:
  base=root/name
  for f in sorted(base.rglob('*')):
   if f.is_file(): out['static_files'][name+'/'+str(f.relative_to(base))]=sha(f.read_bytes())
  index=base/'index.html'; pending=[index] if index.is_file() else []; seen=set()
  while pending:
   f=pending.pop()
   if f in seen: continue
   if not f.is_file(): raise ValueError('missing_active_static_asset')
   seen.add(f)
   if f.suffix not in {'.html','.js','.css'}: continue
   content=f.read_text()
   for ref in re.findall(r'''["']([^"'\s]+\.(?:js|css)(?:\?[^"']*)?)["']''',content):
    ref=ref.split('?',1)[0]
    if ref.startswith(('http:','https:','data:')): continue
    target=(base/ref.lstrip('/')) if ref.startswith('/') else (f.parent/ref)
    # Vite absolute /assets refs and relative chunks remain inside their own build.
    if target.is_file(): pending.append(target)
    elif ref.startswith(('/assets/','./','../')): raise ValueError('missing_active_static_asset')
  out['active_static_graph'][name]={str(f.relative_to(base)):sha(f.read_bytes()) for f in sorted(seen)}
 if imports:
  for p in extra:
   if p.endswith('.py'):
    compile((root/p).read_text(),p,'exec')
    if kind=='cron' and p in {'katrain/web/api/v1/endpoints/kifu.py','katrain/web/core/auth.py','katrain/web/core/migrations.py'}: continue
    if p.startswith('scripts/'):
     runpy.run_path(str(root/p),run_name='_release_import_only')
    else: importlib.import_module(p[:-3].replace('/','.'))
  if kind=='web':
   receiver=runpy.run_path(str(root/'scripts/kifu_incremental.py'),run_name='_release_receiver_import_only')
   if not callable(receiver.get('main')): raise ValueError('receiver_entrypoint_missing')
  out['receiver_import']='ok' if kind=='web' else 'not_applicable_to_producer'
  out['compile_imports']='ok'
  # This is metadata inspection only; no engine connection/create_all/lifespan.
  from katrain.web.core import models_db
  out['rank_models']={}
  for name in ['kifu_player_rank_history','kifu_album_rank_snapshots']:
   table=models_db.Base.metadata.tables[name]
   out['rank_models'][name]={
    'columns':{c.name:{'type':str(c.type),'kind':c.type.__class__.__name__,
                       'length':getattr(c.type,'length',None),'timezone':getattr(c.type,'timezone',None),
                       'nullable':c.nullable,'primary_key':c.primary_key} for c in table.columns},
    'foreign_keys':sorted([{'columns':[f.parent.name],'target_table':f.column.table.name,
                            'target_columns':[f.column.name],'ondelete':f.ondelete or 'NO ACTION'} for f in table.foreign_keys],key=lambda x:x['columns']),
    'unique_columns':sorted([list(c.columns.keys()) for c in table.constraints if c.__class__.__name__=='UniqueConstraint']),
    'check_names':sorted(c.name for c in table.constraints if c.__class__.__name__=='CheckConstraint'),
    'indexes':{i.name:{'columns':list(i.columns.keys()),'unique':i.unique,
                       'predicate':str(i.dialect_options['postgresql'].get('where')) if i.dialect_options['postgresql'].get('where') is not None else None} for i in table.indexes},
   }
 return out
if __name__=='__main__':
 payload=json.loads(sys.stdin.read() or '{}')
 print(json.dumps(probe(payload.get('extra',[]),payload.get('imports',False),payload.get('kind','web')),sort_keys=True))
