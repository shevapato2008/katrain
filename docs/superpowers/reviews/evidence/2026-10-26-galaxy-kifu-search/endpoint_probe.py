"""One isolated process; public endpoint functions under a read-only transaction."""
import asyncio, collections, json, os, re, signal, time
from types import SimpleNamespace
from sqlalchemy import event, text
from katrain.web.core.db import engine, SessionLocal
from katrain.web.api.v1.endpoints import kifu

signal.alarm(25)
queries=[]
stage='setup'
@event.listens_for(engine,'before_cursor_execute')
def before(conn,cursor,statement,parameters,context,executemany):
    context._probe_start=time.perf_counter()
    if len(queries)>350: raise RuntimeError('probe query budget')
@event.listens_for(engine,'after_cursor_execute')
def after(conn,cursor,statement,parameters,context,executemany):
    queries.append(dict(stage=stage,ms=round((time.perf_counter()-context._probe_start)*1000,3),rows=cursor.rowcount,sql=statement,params=parameters))

for name in ['strict_matching_names','strict_selected_event_search_ids','live_event_selections','display_maps','strict_display_maps','report_availability','lookup_album_rank_snapshots']:
    original=getattr(kifu,name)
    def wrap(*args,__name=name,__original=original,**kwargs):
        global stage
        old=stage; stage=__name; start=time.perf_counter(); n=len(queries)
        try:return __original(*args,**kwargs)
        finally:
            print(json.dumps(dict(stage=__name,wall_ms=round((time.perf_counter()-start)*1000,3),queries=len(queries)-n)),flush=True)
            stage=old
    setattr(kifu,name,wrap)

q=os.environ.get('PROBE_QUERY','王星昊') or None
with SessionLocal() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    db.execute(text("SET LOCAL statement_timeout='3000ms'"))
    db.execute(text("SET LOCAL lock_timeout='500ms'"))
    stage='list_count_query_and_summary'
    t=time.perf_counter()
    try:
        response=asyncio.run(kifu.list_kifu_albums(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace())),q=q,page=1,page_size=20,lang='cn',db=db))
        print(json.dumps(dict(endpoint_ms=round((time.perf_counter()-t)*1000,3),q=q,total=response.total,items=len(response.items),sql_count=len(queries),cursor_ms=round(sum(x['ms'] for x in queries),3))),flush=True)
        for x in queries:
            print(json.dumps(dict(stage=x['stage'],ms=x['ms'],rows=x['rows'],sql=re.sub(r'\s+',' ',x['sql'])[:220]),ensure_ascii=False,default=str),flush=True)
        groups=collections.defaultdict(lambda:[0,0,0])
        for x in queries:
            g=groups[x['stage']];g[0]+=1;g[1]+=x['ms'];g[2]+=max(x['rows'],0)
        print(json.dumps(dict(sql_by_stage=groups),default=list),flush=True)
        candidates=[]
        for x in queries:
            if ('FROM kifu_name_changes' in x['sql'] or ('FROM kifu_raw_event_names' in x['sql'] and x['stage']=='strict_matching_names') or ('FROM kifu_albums' in x['sql'] and x['stage']=='list_count_query_and_summary')):
                if len(candidates)<5:candidates.append(x)
        stage='explain_only'
        for i,x in enumerate(candidates):
            rows=db.connection().exec_driver_sql('EXPLAIN (FORMAT JSON) '+x['sql'],x['params']).scalar()
            print(json.dumps(dict(explain=i,source_stage=x['stage'],sql_ms=x['ms'],plan=rows),ensure_ascii=False,default=str),flush=True)
    except Exception as exc:
        print(json.dumps(dict(error=type(exc).__name__,message=str(exc)[:150],queries=len(queries))),flush=True)
    finally:db.rollback()
