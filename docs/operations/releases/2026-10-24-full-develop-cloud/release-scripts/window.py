import json,sys,datetime
from sqlalchemy import text
from katrain.cron.db import engine
marker='full-develop-495d0284c-20261024-release-window';name='kifu_ingest';action=sys.argv[1]
with engine.begin() as c:
 row=c.execute(text('select * from cron_job_controls where job_name=:n for update'),{'n':name}).mappings().first()
 if action=='pause':
  original=dict(row) if row else None
  if row and row['paused']:
   print(json.dumps({'owned':False,'original':original},default=str));sys.exit(0)
  if row:c.execute(text('update cron_job_controls set paused=true,reason=:r,changed_at=:t,changed_by=:b where job_name=:n'),{'n':name,'r':marker,'t':datetime.datetime.now(datetime.timezone.utc),'b':'release-agent'})
  else:c.execute(text('insert into cron_job_controls(job_name,paused,reason,changed_at,changed_by) values(:n,true,:r,:t,:b)'),{'n':name,'r':marker,'t':datetime.datetime.now(datetime.timezone.utc),'b':'release-agent'})
  result={'owned':True,'original':original,'marker':marker}
 elif action=='resume':
  state=json.loads(sys.argv[2]);assert row and row['paused'] and row['reason']==marker,'Control changed; refuse to overwrite another operator'
  if state['original'] is None:c.execute(text('delete from cron_job_controls where job_name=:n and reason=:r'),{'n':name,'r':marker})
  else:
   old=state['original'];c.execute(text('update cron_job_controls set paused=:paused,reason=:reason,changed_at=:changed_at,changed_by=:changed_by where job_name=:job_name'),old)
  result={'restored_original_control':True}
 else:raise ValueError('unknown action')
print(json.dumps(result,default=str))
