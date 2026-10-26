#!/usr/bin/env python3
"""Controller-gated final data operator. Installing/preflight never exports or restores."""
import argparse,datetime,hashlib,hmac,json,os,pathlib,re,secrets,shutil,socket,stat,subprocess,sys,time

BASE=pathlib.Path('/var/lib/ucloud-migration-20261027')
SOURCE='10-60-219-118';TARGET='10-60-162-188';MIN_FREE=15*1024**3
PG={
 'katrain-ucloud-postgres-1':('katrain-ucloud_postgres-data','15','sha256:3d0f7584ed7d04e27fa050d6683a74746608faf21f202be78460d679cc56461f'),
 'platform-postgres':('lobby-pgdata','15','sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b'),
 'smartbox-kifu-postgres-1':('smartbox-kifu_kifu_db','16','sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777'),
 'pitch-booking-postgres-1':('pitch-booking_postgres_data','17','sha256:d4bb0a8c1b7bb2e29f976d099e7bfb9a5d8858cffe9e46b35cd302cd1f1f8168')}
WRITERS=['katrain-ucloud-katrain-web-1','katrain-ucloud-katrain-cron-1',
 'katrain-ucloud-katrain-admin-1','smartbox-admin-admin-console-1','smartbox-platform',
 'pitch-booking-api-1','pitch-booking-worker-1','pitch-booking-caddy-1',
 'smartbox-kifu-api-1','smartbox-kifu-api-b-1','katrain-ucloud-minio-1']
GPU={'katrain-ucloud-katago-web-1','katrain-ucloud-katago-cron-1'}
KEYS=pathlib.Path('/home/kifu-receiver/.ssh/authorized_keys')
PHASE='final_offline_after_writer_fence'
WORK=None
os.umask(0o077)

class GateError(Exception):pass
def need(value,reason):
 if not value:raise GateError(reason)
def sha(data):return hashlib.sha256(data).hexdigest()
def digest(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as f:
  for part in iter(lambda:f.read(8*1024**2),b''):h.update(part)
 return h.hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def private_json(path,value):
 path=pathlib.Path(path);tmp=path.with_suffix('.tmp')
 with tmp.open('w') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')
 tmp.chmod(0o600);tmp.replace(path)
def checked_private(path):
 path=pathlib.Path(path);st=path.lstat()
 need(stat.S_ISREG(st.st_mode) and st.st_uid==0 and stat.S_IMODE(st.st_mode)==0o600,'root_0600_file_required:'+path.name)
 return json.loads(path.read_text())
def disk():need(shutil.disk_usage('/').free>=MIN_FREE,'root_free_below_15GiB')
def command(argv,input_bytes=None,allow=False,label='command',input_path=None):
 disk()
 if input_path is not None:
  with pathlib.Path(input_path).open('rb') as inp:r=subprocess.run(argv,stdin=inp,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 else:r=subprocess.run(argv,input=input_bytes,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if WORK is not None:
  safe=re.sub('[^a-zA-Z0-9_.-]','_',label)
  with (WORK/(safe+'.private.log')).open('ab') as f:
   f.write(r.stderr)
 if r.returncode and not allow:raise GateError('command_failed:'+label+':exit='+str(r.returncode))
 return r.returncode,r.stdout
def inspect(name):return json.loads(command(['docker','inspect',name],label='inspect')[1])[0]
def env_user(name):
 c=inspect(name);e=dict(x.split('=',1) for x in c['Config']['Env'] if '=' in x)
 return c,e.get('POSTGRES_USER','postgres'),e.get('PGDATA','/var/lib/postgresql/data')
def dex(name,args,input_bytes=None,label='pg',allow=False,input_path=None):
 return command(['docker','exec']+(['-i'] if input_bytes is not None or input_path is not None else [])+[name]+args,input_bytes,allow,label,input_path)
def query(name,db,text):
 _,user,_=env_user(name)
 data=dex(name,['psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-U',user,'-d',db],
  ('BEGIN READ ONLY; SET LOCAL statement_timeout=\'60s\';\n'+text+'\nCOMMIT;\n').encode(),label=name+'-query')[1]
 return json.loads(data.decode().strip())
def names(name):return query(name,'template1',"SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate;")
def receiver_processes():
 matches=[]
 for p in pathlib.Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:argv=(p/'cmdline').read_bytes().split(b'\0')
  except (OSError,PermissionError):continue
  if b'receive' in argv and any(os.path.basename(a)==b'kifu_incremental.py' for a in argv if a):matches.append(int(p.name))
 return matches
def receiver_gate():
 need(KEYS.exists() and KEYS.stat().st_size==0,'receiver_active_keys_must_exist_and_be_empty')
 need(not receiver_processes(),'receiver_receive_process_present')
def pg_gate(running=True):
 for name,(volume,major,image) in PG.items():
  c=inspect(name);need(c['Image']==image,'pg_immutable_image_mismatch:'+name)
  need(c['State']['Running']==running,'pg_running_state_mismatch:'+name)
  need(len(c['Mounts'])==1 and c['Mounts'][0].get('Name')==volume,'pg_original_volume_mismatch:'+name)
  if running:
   p=query(name,'template1',"SELECT json_build_object('prepared',(SELECT count(*) FROM pg_prepared_xacts), 'clients',(SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()),'major',current_setting('server_version_num')::int/10000);")
   need(p['prepared']==0 and p['clients']==0,'pg_has_prepared_or_client_sessions:'+name)
   need(str(p['major'])==major,'pg_major_mismatch:'+name)
def controllers_only():
 running=command(['docker','ps','--format','{{.Names}}'],label='running-containers')[1].decode().splitlines()
 need(set(running).issubset(set(PG)|GPU),'non_pg_gpu_container_running')
def source_gate(fence):
 need(socket.gethostname()==SOURCE,'wrong_source_hostname')
 for name in WRITERS:
  c=inspect(name);f=fence['SourceContainers'].get(name)
  need(f is not None,'fence_missing_writer:'+name)
  need(c['Id']==f['ContainerID'] and c['Image']==f['ImageID'],'source_writer_identity_changed:'+name)
  need(not c['State']['Running'] and c['State']['Status']=='exited' and c['State']['Pid']==0,'source_writer_not_exited:'+name)
  need(f.get('Running') is False and f.get('Status')=='exited' and f.get('PID')==0,'fence_writer_state_invalid:'+name)
  need(c['State']['FinishedAt']==f['FinishedAt'],'source_writer_restarted_since_fence:'+name)
 controllers_only();receiver_gate();pg_gate(True)
def target_gate(pg_running=True):
 need(socket.gethostname()==TARGET,'wrong_target_hostname')
 controllers_only();receiver_gate();pg_gate(pg_running)
 rc,_=command(['systemctl','is-active','nginx'],allow=True,label='nginx-state')
 need(rc!=0,'public_nginx_active')
 addresses=json.loads(command(['ip','-j','address','show'],label='address-state')[1])
 need(not any(a.get('local')=='10.8.0.3' for i in addresses for a in i.get('addr_info',[])),'wg_identity_already_taken_over')
 _,listeners=command(['ss','-H','-lnt'],label='listener-state')
 for line in listeners.decode().splitlines():
  fields=line.split()
  if len(fields)<4:continue
  local=fields[3];port=local.rsplit(':',1)[-1]
  if port in ('80','443','18080','18443'):
   need(local.startswith('127.') or local.startswith('[::1]:'),'public_80_or_443_listener')
def authority(args):
 need(os.geteuid()==0,'root_required')
 need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',args.window_id or '') is not None,'invalid_window_id')
 need(args.go=='APPROVED:'+args.window_id,'explicit_matching_go_required')
 expected=BASE/('source-fence-'+args.window_id+'.private.json')
 need(pathlib.Path(args.fence_file)==expected,'fixed_window_fence_path_required')
 need(re.fullmatch('[0-9a-f]{64}',args.fence_sha or '') is not None,'pinned_fence_sha_required')
 f=checked_private(expected);need(digest(expected)==args.fence_sha,'fence_sha_mismatch')
 need(f.get('Schema')==1 and f.get('WindowID')==args.window_id and f.get('Owner')=='migration-controller','fence_schema_or_owner_mismatch')
 need(f.get('SourceHostname')==SOURCE and f.get('TargetHostname')==TARGET and f.get('OldWritersFenced') is True,'fence_hosts_or_truth_invalid')
 need(all(f.get(k)==0 for k in ('ReceiverActiveKeysBytes','ReceiverProcesses','PreparedTransactions','WritableClientTransactions')),'fence_nonzero_writers')
 need(set(f.get('SourceContainers',{}))==set(WRITERS),'fence_writer_inventory_mismatch')
 need(re.fullmatch('[0-9a-f]{64}',f.get('ControlStateSHA256','')) is not None,'missing_control_plan_sha')
 t=f.get('TestWriterGate',{})
 need(t.get('ExpiresUnix',0)>time.time(),'test_writer_gate_expired')
 for key in ('ReadySHA256','HolderContainerID','SourceDevelopSHA','StageLockInode'):need(t.get(key) is not None,'missing_test_gate_field:'+key)
 need(bool(f.get('RecordedUTC')),'missing_fence_recorded_utc')
 return f
def remote(args,action,proof_nonce=None):
 need(socket.gethostname()==TARGET,'remote_probe_from_target_only')
 cmd=['ssh','-i',str(BASE/'transfer_key'),'-oIdentitiesOnly=yes','-oBatchMode=yes','-oStrictHostKeyChecking=yes',
  '-oUserKnownHostsFile='+str(BASE/'transfer_known_hosts'),'-oConnectTimeout=10','ubuntu@10.60.219.118',
  'sudo','-n','python3','-',action,'--window-id',args.window_id,'--fence-file',args.fence_file,
  '--fence-sha',args.fence_sha,'--go',args.go]
 if proof_nonce is not None:cmd+=['--proof-nonce',proof_nonce]
 _,out=command(cmd,pathlib.Path(__file__).read_bytes(),label='source-'+action)
 return json.loads(out)
def normalized_schema(name,db):
 _,user,_=env_user(name)
 out=dex(name,['pg_dump','-U',user,'--schema-only','--create','--dbname',db],label=name+'-schema')[1]
 # New pg_dump uses a random psql restrict token; it is not schema content.
 out=re.sub(rb'(?m)^\\(?:un)?restrict [^\r\n]+',lambda _:b'\\restrict <TOKEN>',out)
 return sha(out)
ROLE_SQL="""SELECT json_build_object('roles',(SELECT json_agg(t ORDER BY rolname) FROM
 (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolconnlimit,
 rolbypassrls,(rolvaliduntil AT TIME ZONE 'UTC')::text AS rolvaliduntil,
 (SELECT coalesce(json_agg(json_build_object('database',coalesce(d.datname,''),'settings',s.setconfig) ORDER BY coalesce(d.datname,'')),'[]'::json)
  FROM pg_db_role_setting s LEFT JOIN pg_database d ON d.oid=s.setdatabase WHERE s.setrole=a.oid) AS role_settings
 FROM pg_authid a WHERE rolname !~ '^pg_') t), 'membership',(SELECT coalesce(json_agg(t ORDER BY role,member,grantor),'[]'::json) FROM
 (SELECT r.rolname AS role,m.rolname AS member,g.rolname AS grantor,admin_option,
 to_jsonb(a)-'oid'-'roleid'-'member'-'grantor' AS membership_options FROM pg_auth_members a
 JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member JOIN pg_roles g ON g.oid=a.grantor) t));"""
OBJECT_SQL="""SELECT json_build_object(
 'databases',(SELECT json_agg(t ORDER BY datname) FROM (SELECT datname,pg_get_userbyid(datdba) owner,datacl::text,encoding,datcollate,datctype FROM pg_database WHERE NOT datistemplate) t),
 'objects',(SELECT coalesce(json_agg(t ORDER BY schema,name,kind),'[]'::json) FROM (SELECT n.nspname AS schema,c.relname AS name,c.relkind::text AS kind,pg_get_userbyid(c.relowner) owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','S','v','m')) t),
 'sequences',(SELECT coalesce(json_agg(t ORDER BY schemaname,sequencename),'[]'::json) FROM (SELECT schemaname,sequencename,sequenceowner,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname !~ '^pg_') t),
 'extensions',(SELECT json_agg(t ORDER BY extname) FROM (SELECT extname,extversion,pg_get_userbyid(extowner) owner FROM pg_extension) t));"""
NATIVE_SQL="""SELECT json_build_object('batches',(SELECT json_agg(t ORDER BY id) FROM
 (SELECT id,status,bundle_sha256,reviewed_artifact->>'publication_key' publication_key,
 encode(sha256(convert_to(reviewed_artifact::text,'UTF8')),'hex') artifact_sha256,
 md5(reviewed_artifact::text) artifact_md5,octet_length(reviewed_artifact::text) artifact_bytes
 FROM kifu_name_batches WHERE id IN (931,932)) t),
 'rank_snapshots',(SELECT json_agg(t ORDER BY album_id,side) FROM
 (SELECT album_id,side,snapshot_sha256,snapshot->>'content_sha256' content_sha256,
 snapshot->>'display_rank' display_rank,publication_key,native_batch_id,
 encode(sha256(convert_to(snapshot::text,'UTF8')),'hex') snapshot_text_sha256
 FROM kifu_album_rank_snapshots WHERE album_id IN (178743,178744,178745)) t));"""
def fingerprints():
 result={}
 for name in PG:
  r={'roles':query(name,'template1',ROLE_SQL),'databases':{}}
  for db in names(name):
   meta=query(name,db,OBJECT_SQL);meta['schema_sha256']=normalized_schema(name,db);meta['counts']={}
   wanted={'users','kifu_albums','tsumego_problems','tutorial_books','tutorial_figures','kifu_album_rank_snapshots','kifu_player_rank_history'}
   for o in meta['objects']:
    if o['kind'] in ('r','p') and o['name'] in wanted:
     table='"'+o['schema'].replace('"','""')+'"."'+o['name'].replace('"','""')+'"'
     meta['counts'][o['schema']+'.'+o['name']]=query(name,db,'SELECT to_json(count(*)) FROM '+table+';')
   if name=='katrain-ucloud-postgres-1' and db=='katrain_prod_20260725':
    meta['native']=query(name,db,NATIVE_SQL)
    need(len(meta['native']['batches'] or [])==2 and len(meta['native']['rank_snapshots'] or [])==6,'protected_native_rows_missing')
    need([x['publication_key'] for x in meta['native']['batches']]==['rank-only-page-coverage-20261026-v1','rank-only-current-page-tail-20261026-v1'],'protected_native_pubkey_mismatch')
    need(all(x['snapshot_sha256']==x['content_sha256'] for x in meta['native']['rank_snapshots']),'rank_snapshot_hash_field_mismatch')
   r['databases'][db]=meta
  result[name]=r
 return result
def archive_record(path,**fields):return dict(fields,file=str(path.relative_to(WORK)),bytes=path.stat().st_size,sha256=digest(path))
def write_command_file(argv,path,label):
 need(not path.exists() and not pathlib.Path(str(path)+'.partial').exists(),'refuse_archive_overwrite')
 disk();part=pathlib.Path(str(path)+'.partial')
 with part.open('xb') as out, (WORK/(label+'.stderr.private.log')).open('ab') as err:
  p=subprocess.Popen(['nice','-n','10']+argv,stdout=out,stderr=err)
  while p.poll() is None:
   if shutil.disk_usage('/').free<MIN_FREE:
    p.terminate();p.wait();raise GateError('root_free_below_15GiB')
   time.sleep(1)
  need(p.returncode==0,'archive_command_failed:'+label)
 part.replace(path);path.chmod(0o600)
def export_configs(name):
 _,_,data=env_user(name)
 q="SELECT json_build_object('data_directory',current_setting('data_directory'),'config_file',current_setting('config_file'),'hba_file',current_setting('hba_file'),'ident_file',current_setting('ident_file'),'ssl',current_setting('ssl'),'ssl_cert_file',current_setting('ssl_cert_file'),'ssl_key_file',current_setting('ssl_key_file'),'ssl_ca_file',current_setting('ssl_ca_file'),'ssl_crl_file',current_setting('ssl_crl_file'),'ssl_crl_dir',current_setting('ssl_crl_dir'),'sourcefiles',(SELECT json_agg(DISTINCT sourcefile) FROM pg_file_settings WHERE sourcefile IS NOT NULL));"
 info=query(name,'template1',q);need(info['data_directory']==data,'unexpected_data_directory:'+name)
 info['settings_whitelist']=query(name,'template1',"SELECT json_agg(t ORDER BY name) FROM (SELECT name,setting,unit FROM pg_settings WHERE name IN ('server_version','listen_addresses','port','max_connections','shared_buffers','work_mem','maintenance_work_mem','effective_cache_size','wal_level','max_wal_senders','max_replication_slots','max_prepared_transactions','checkpoint_timeout','max_wal_size','min_wal_size','password_encryption','ssl','timezone','log_statement','log_min_duration_statement')) t;")
 errors=query(name,'template1',"SELECT json_build_object('file_errors',(SELECT count(*) FROM pg_file_settings WHERE error IS NOT NULL),'pending_restart',(SELECT coalesce(json_agg(name ORDER BY name),'[]'::json) FROM pg_settings WHERE pending_restart));")
 need(errors['file_errors']==0 and not errors['pending_restart'],'source_config_errors_or_pending_restart_require_controller_review')
 paths=set(info['sourcefiles'] or [])|{info['config_file'],info['hba_file'],info['ident_file'],data+'/postgresql.auto.conf'}
 if info['ssl']=='on':
  need(not info['ssl_crl_dir'],'ssl_crl_directory_requires_explicit_controller_handling')
  paths|={info[k] for k in ('ssl_cert_file','ssl_key_file','ssl_ca_file','ssl_crl_file') if info[k]}
 records=[]
 for index,original_path in enumerate(sorted(paths)):
  absolute=original_path if original_path.startswith('/') else data+'/'+original_path
  rc,res=dex(name,['readlink','-f','--',absolute],label=name+'-config-path',allow=True)
  if rc and absolute==data+'/postgresql.auto.conf':continue
  need(rc==0,'config_path_not_resolvable:'+name)
  resolved=res.decode().strip()
  rc,_=dex(name,['test','-f',resolved],label=name+'-config-file',allow=True)
  if rc and absolute==data+'/postgresql.auto.conf':continue
  need(rc==0,'config_not_regular_file:'+name)
  attrs=dex(name,['stat','-c','%u %g %a',resolved],label=name+'-config-mode')[1].decode().strip().split()
  dst=WORK/'configs'/name/(str(index).zfill(3)+'.bin');dst.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  write_command_file(['docker','exec',name,'cat','--',resolved],dst,name+'-config-'+str(index))
  # Materialize the referenced path, while retaining symlink resolution evidence.
  # References resolving outside PGDATA are explicitly gated, never blindly copied.
  relative=str(pathlib.PurePosixPath(absolute).relative_to(data)) if absolute.startswith(data+'/') and resolved.startswith(data+'/') else None
  records.append(archive_record(dst,container=name,original_path=absolute,resolved_path=resolved,volume_relative_path=relative,source_uid=int(attrs[0]),source_gid=int(attrs[1]),source_mode=attrs[2],external=relative is None))
 return {'paths':info,'files':records}
def load_manifest(args):
 root=BASE/('final-db-'+args.window_id);path=root/'manifest.json';m=checked_private(path)
 need(m.get('Status')=='verified_final_export' and m.get('Phase')==PHASE and m.get('WindowID')==args.window_id,'final_manifest_not_verified')
 need(m.get('SourceFenceSHA256')==args.fence_sha and m.get('SourceHostname')==SOURCE,'manifest_source_fence_mismatch')
 need(len(m['databases'])==13 and len(m['globals'])==4,'final_archive_inventory_mismatch')
 for record in m['databases']+m['globals']+[f for v in m['configs'].values() for f in v['files']]:
  p=root/record['file'];need(p.resolve().is_relative_to(root.resolve()),'manifest_path_escape')
  need(p.stat().st_size==record['bytes'] and digest(p)==record['sha256'],'final_file_hash_or_size_mismatch')
 return root,m
def export(args,fence):
 global WORK
 source_gate(fence);root=BASE/('final-db-'+args.window_id);need(not root.exists(),'fresh_final_directory_required')
 root.mkdir(mode=0o700);WORK=root
 m={'Schema':1,'Status':'exporting','Phase':PHASE,'WindowID':args.window_id,'SourceHostname':SOURCE,'SourceFenceSHA256':args.fence_sha,'StartedUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'databases':[],'globals':[],'configs':{}}
 private_json(root/'manifest.json',m)
 try:
  for name in PG:
   _,user,_=env_user(name)
   g=root/(name+'-globals.sql');write_command_file(['docker','exec',name,'pg_dumpall','-U',user,'--globals-only'],g,name+'-globals')
   m['globals'].append(archive_record(g,container=name))
   for db in names(name):
    need(re.fullmatch('[A-Za-z0-9_]+',db) is not None,'unsafe_database_filename')
    p=root/(name+'--'+db+'.pgcustom')
    write_command_file(['docker','exec',name,'pg_dump','-U',user,'--format=custom','--compress=1','--dbname',db],p,name+'-'+db)
    toc=command(['docker','exec','-i',name,'pg_restore','--list'],input_path=p,label=name+'-'+db+'-toc')[1].decode()
    versions=re.findall(r'Dumped (?:from database|by pg_dump) version: ([^\n]+)',toc)
    need(len(versions)==2 and all(v.split('.')[0]==PG[name][1] for v in versions),'dump_toc_major_mismatch')
    m['databases'].append(archive_record(p,container=name,database=db,toc_exit=0,versions=versions))
    private_json(root/'manifest.json',m)
   m['configs'][name]=export_configs(name)
  need(len(m['databases'])==13,'source_database_count_changed_requires_controller_review')
  m['fingerprints']=fingerprints();m['FingerprintSHA256']=sha(canonical(m['fingerprints']))
  source_gate(fence);m['Status']='verified_final_export';m['FinishedUTC']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  private_json(root/'manifest.json',m)
  print(json.dumps({'Status':m['Status'],'WindowID':args.window_id,'ManifestSHA256':digest(root/'manifest.json'),'FingerprintSHA256':m['FingerprintSHA256']}))
 except BaseException as e:
  m['Status']='failed_final_export';m['FailureType']=type(e).__name__;private_json(root/'manifest.json',m);raise
def source_verify(args,fence):
 source_gate(fence);root,m=load_manifest(args);live=fingerprints();source_gate(fence)
 need(sha(canonical(live))==m['FingerprintSHA256'],'source_changed_after_final_export')
 need(re.fullmatch('[0-9a-f]{64}',args.proof_nonce or '') is not None,'ephemeral_role_password_proof_nonce_required')
 proof=role_password_proof(args.proof_nonce)
 print(json.dumps({'Status':'verified_still_fenced','WindowID':args.window_id,'FingerprintSHA256':m['FingerprintSHA256'],'ManifestSHA256':digest(root/'manifest.json'),'EphemeralRolePasswordProof':proof}))
def role_password_proof(nonce):
 # Actual role password hashes remain in process memory; only a nonce-bound proof crosses SSH.
 values={name:query(name,'template1',"SELECT json_agg(t ORDER BY rolname) FROM (SELECT rolname,rolpassword FROM pg_authid WHERE rolname !~ '^pg_') t;") for name in PG}
 return hmac.new(bytes.fromhex(nonce),canonical(values),hashlib.sha256).hexdigest()
def apply(args,fence):
 global WORK
 target_gate(True);probe=remote(args,'source-audit');need(probe['Status']=='verified_source_fence','source_not_fenced')
 root,m=load_manifest(args)
 need(bool(args.transfer_receipt),'controller_verified_transfer_receipt_required')
 tr=checked_private(args.transfer_receipt)
 need(tr.get('WindowID')==args.window_id and tr.get('Status')=='verified_final_archives' and tr.get('SourceFenceSHA256')==args.fence_sha and tr.get('ManifestSHA256')==digest(root/'manifest.json'),'controller_transfer_receipt_mismatch')
 WORK=BASE/'final-data'/('apply-'+args.window_id);need(not WORK.exists(),'refuse_apply_rerun_after_partial_or_completed_apply');WORK.mkdir(mode=0o700)
 receipt={'Schema':1,'Status':'applying','Phase':PHASE,'WindowID':args.window_id,'SourceFenceSHA256':args.fence_sha,'ManifestSHA256':digest(root/'manifest.json'),'databases':[]}
 private_json(WORK/'receipt.private.json',receipt)
 try:
  plans=[]
  for name in PG:
   _,user,_=env_user(name);g=next(x for x in m['globals'] if x['container']==name)
   content=(root/g['file']).read_text();need('CREATE TABLESPACE ' not in content,'external_tablespace_requires_controller_review')
   pattern=re.compile(r'^CREATE ROLE ("(?:[^"]|"")*"|[^ ;]+);$',re.M)
   decode=lambda v:v[1:-1].replace('""','"') if v.startswith('"') else v
   statements=[(x.group(0),decode(x.group(1))) for x in pattern.finditer(content)]
   source_roles={x['rolname'] for x in m['fingerprints'][name]['roles']['roles']}
   need({x[1] for x in statements}==source_roles,'globals_role_inventory_incompatible')
   existing=set(query(name,'template1',"SELECT json_agg(rolname ORDER BY rolname) FROM pg_roles WHERE rolname !~ '^pg_';"))
   need(existing.issubset(source_roles) and user in existing,'target_role_inventory_incompatible')
   remove={line for line,role in statements if role in existing}
   need(len(remove)==len(existing),'existing_role_create_filter_not_exact')
   filtered='\n'.join(line for line in content.split('\n') if line not in remove)
   dbs=[d for d in m['databases'] if d['container']==name]
   need(set(names(name))=={d['database'] for d in dbs},'target_database_inventory_incompatible')
   plans.append((name,user,filtered,dbs))
  # Validate every target's role/database compatibility before the first database write.
  target_gate(True)
  for name,user,filtered,dbs in plans:
   dex(name,['psql','-X','-v','ON_ERROR_STOP=1','--single-transaction','-U',user,'-d','template1'],filtered.encode(),label=name+'-globals-restore')
   for d in dbs:
    # Current real PG containers have no archive bind. Streaming avoids another archive copy;
    # pg_restore requires a seekable archive for parallel restore, so this path uses one job.
    dex(name,['pg_restore','--exit-on-error','--clean','--if-exists','--create','--jobs=1','-U',user,'-d','template1'],input_path=root/d['file'],label=name+'-'+d['database']+'-restore')
    receipt['databases'].append({'container':name,'database':d['database'],'restore_exit':0});private_json(WORK/'receipt.private.json',receipt)
  target_gate(True);nonce=secrets.token_hex(32);source=remote(args,'source-verify',nonce)
  need(hmac.compare_digest(source['EphemeralRolePasswordProof'],role_password_proof(nonce)),'final_role_passwords_mismatch')
  target=fingerprints();private_json(WORK/'target-fingerprints.private.json',target)
  actual=sha(canonical(target));need(source['FingerprintSHA256']==m['FingerprintSHA256']==actual,'final_source_target_fingerprints_mismatch')
  target_gate(True);need(remote(args,'source-audit')['Status']=='verified_source_fence','source_fence_lost_after_apply')
  receipt.update(Status='verified_final_logical_data',FingerprintSHA256=actual,RolePasswordsVerifiedInMemory=True,ConfigsStatus='pending_controller_pg_stop_and_explicit_config_copy',FinishedUTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
  private_json(WORK/'receipt.private.json',receipt)
  print(json.dumps({k:receipt[k] for k in ('Status','WindowID','FingerprintSHA256','ConfigsStatus')}))
 except BaseException as e:
  receipt.update(Status='failed_final_apply',FailureType=type(e).__name__);private_json(WORK/'receipt.private.json',receipt);raise
def copy_configs(args,fence):
 target_gate(False);need(remote(args,'source-audit')['Status']=='verified_source_fence','source_not_fenced')
 root,m=load_manifest(args);logical=checked_private(BASE/'final-data'/('apply-'+args.window_id)/'receipt.private.json')
 need(logical.get('Status')=='verified_final_logical_data','verified_final_logical_restore_required')
 result={'Schema':1,'WindowID':args.window_id,'SourceFenceSHA256':args.fence_sha,'Phase':PHASE,'Status':'copying_stopped_pg_configs','files':[],'external_required':[]}
 for name in PG:
  for f in m['configs'][name]['files']:
   if f['external']:result['external_required'].append({'container':name,'path':f['resolved_path'],'sha256':f['sha256']})
 out=BASE/'final-data'/('config-copy-'+args.window_id+'.private.json')
 need(not out.exists(),'refuse_config_copy_rerun_without_controller_review')
 private_json(out,result)
 if result['external_required']:
  result['Status']='blocked_external_config_paths_require_controller_resolution';private_json(out,result)
 need(not result['external_required'],'external_config_paths_require_controller_explicit_resolution_before_copy')
 for name,(vol,major,_) in PG.items():
  v=json.loads(command(['docker','volume','inspect',vol],label='volume-inspect')[1])[0];mount=pathlib.Path(v['Mountpoint'])
  need((mount/'PG_VERSION').read_text().strip()==major,'stopped_pg_volume_major_mismatch')
  for f in m['configs'][name]['files']:
   relative=pathlib.PurePosixPath(f['volume_relative_path']);need(not relative.is_absolute() and '..' not in relative.parts,'unsafe_config_relative_path')
   dst=mount.joinpath(*relative.parts);need(dst.resolve().is_relative_to(mount.resolve()),'config_target_symlink_escape')
   missing=[];parent=dst.parent
   while not parent.exists():missing.append(parent);parent=parent.parent
   for parent in reversed(missing):parent.mkdir(mode=0o700);os.chown(parent,70,70)
   src=root/f['file']
   tmp=dst.with_name(dst.name+'.migration-'+args.window_id);need(not tmp.exists(),'stale_config_copy_temp')
   with src.open('rb') as inp,tmp.open('xb') as target_stream:shutil.copyfileobj(inp,target_stream)
   os.chown(tmp,70,70);tmp.chmod(int(f['source_mode'],8));tmp.replace(dst)
   need(digest(dst)==f['sha256'] and dst.stat().st_uid==70,'copied_config_checksum_or_uid_mismatch')
   result['files'].append({'container':name,'volume_relative_path':str(relative),'sha256':f['sha256'],'uid':70,'mode':f['source_mode']})
   private_json(out,result)
 target_gate(False);result['Status']='copied_configs_while_pg_stopped_pending_controller_restart_validation'
 private_json(out,result)
 print(json.dumps({'Status':result['Status'],'WindowID':args.window_id,'files':len(result['files'])}))
def preflight():
 need(socket.gethostname()==TARGET and os.geteuid()==0,'target_root_preflight_only')
 blockers=[]
 try:target_gate(True)
 except GateError as e:blockers.append(str(e))
 result={'Status':'prepared_not_executed','TargetHostname':TARGET,'CurrentFinalApplyBlockers':blockers,
  'FinalExportPerformed':False,'FinalRestorePerformed':False,'FinalConfigCopyPerformed':False,
  'Authority':'No controller window/fence/GO receipt was created by this operator.'}
 print(json.dumps(result))
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','source-audit','source-export','source-verify','target-apply','target-copy-configs'])
 for key in ('window-id','fence-file','fence-sha','go','transfer-receipt','proof-nonce'):p.add_argument('--'+key)
 args=p.parse_args()
 if args.action=='preflight':preflight();return
 fence=authority(args)
 if args.action=='source-audit':source_gate(fence);print(json.dumps({'Status':'verified_source_fence','WindowID':args.window_id}));return
 {'source-export':export,'source-verify':source_verify,'target-apply':apply,'target-copy-configs':copy_configs}[args.action](args,fence)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if isinstance(e,SystemExit):raise
  # No traceback/SQL/environment is sent to stdout or journal.
  print(json.dumps({'Status':'blocked_or_failed','FailureType':type(e).__name__,'Reason':str(e) if isinstance(e,GateError) else 'private_operator_error'}),file=sys.stderr)
  sys.exit(1)
