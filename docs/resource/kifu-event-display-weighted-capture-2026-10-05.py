import os,json,time,datetime
from sqlalchemy import create_engine,text
start=time.monotonic()
with create_engine(os.environ['KATRAIN_DATABASE_URL']).connect() as c:
 t=c.begin();c.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'));c.execute(text("SET LOCAL statement_timeout='120s'"));c.execute(text("SET LOCAL lock_timeout='2s'"))
 meta=dict(c.execute(text("SELECT current_timestamp::text AS captured_at, txid_current_snapshot()::text AS snapshot, current_setting('transaction_read_only') AS read_only")).mappings().one())
 def rows(q):return [dict(r) for r in c.execute(text(q)).mappings()]
 data={'meta':meta,'totals':rows("SELECT count(*) AS games,count(event) AS with_event,count(*) FILTER (WHERE event IS NOT NULL AND btrim(event)<>'') AS nonblank_event,count(*) FILTER (WHERE event_id IS NOT NULL) AS linked FROM kifu_albums")[0],
 'raw_groups':rows("SELECT a.event AS raw,a.event_id,r.id AS raw_event_id,r.category,r.parsed_data->>'series_core' AS core,count(*) AS games FROM kifu_albums a LEFT JOIN kifu_raw_event_values r ON r.raw_value=a.event GROUP BY a.event,a.event_id,r.id,r.category,r.parsed_data->>'series_core' ORDER BY count(*) DESC,a.event"),
 'events':rows('SELECT id,canonical_name FROM kifu_events ORDER BY id'),
 'aliases':rows('SELECT event_id,alias,normalized_alias FROM kifu_event_aliases ORDER BY event_id,alias'),
 'event_names':rows("SELECT event_id,lang,display_name,status FROM kifu_event_names WHERE lang='zh' ORDER BY event_id"),
 'raw_names':rows("SELECT raw_event_id,lang,display_name,status FROM kifu_raw_event_names WHERE lang='zh' ORDER BY raw_event_id")}
 t.rollback();data.update(transaction_end='ROLLBACK',database_writes=0,elapsed_seconds=round(time.monotonic()-start,3));print(json.dumps(data,ensure_ascii=False,separators=(',',':')))
