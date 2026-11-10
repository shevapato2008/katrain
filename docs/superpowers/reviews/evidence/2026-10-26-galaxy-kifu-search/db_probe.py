import json, time, socket, re
from sqlalchemy import text
from katrain.web.core.db import engine

with engine.connect() as c:
    tx=c.begin()
    c.execute(text('SET TRANSACTION READ ONLY'))
    c.execute(text("SET LOCAL statement_timeout='3000ms'"))
    c.execute(text("SET LOCAL lock_timeout='500ms'"))
    statements={
      'database_sizes': "SELECT pg_database_size(current_database()) bytes, pg_total_relation_size('kifu_albums') album_total_bytes, pg_relation_size('kifu_albums') album_heap_bytes",
      'album_stats': "SELECT n_live_tup,n_dead_tup,last_analyze,last_autoanalyze,seq_scan,idx_scan FROM pg_stat_user_tables WHERE relname='kifu_albums'",
      'counts': "SELECT count(*) total,count(*) FILTER (WHERE duplicate_of_id IS NULL AND list_hidden_reason IS NULL) visible FROM kifu_albums",
      'indexes': "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE tablename IN ('kifu_albums','kifu_player_names','kifu_event_names','kifu_name_changes','kifu_name_batches','kifu_raw_player_names') ORDER BY tablename,indexname",
      'players': "SELECT player_id,lang,display_name,status,generation_rule_version FROM kifu_player_names WHERE display_name='王星昊'",
      'activity_summary': "SELECT state,wait_event_type,wait_event,count(*) FROM pg_stat_activity WHERE datname=current_database() GROUP BY state,wait_event_type,wait_event",
      'settings': "SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','effective_cache_size','work_mem','max_connections','log_min_duration_statement','track_io_timing','max_parallel_workers_per_gather')",
      'extensions': 'SELECT extname FROM pg_extension',
    }
    for name,sql in statements.items():
        t=time.perf_counter()
        try:
            rows=[dict(r) for r in c.execute(text(sql)).mappings()]
            print(json.dumps(dict(probe=name,ms=round((time.perf_counter()-t)*1000,3),rows=rows),ensure_ascii=False,default=str),flush=True)
        except Exception as exc:
            print(json.dumps(dict(probe=name,error=type(exc).__name__)),flush=True)
            break
    tx.rollback()
