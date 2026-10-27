import json,signal,time
from sqlalchemy import text
from katrain.web.core.db import engine
signal.alarm(15)
queries={
 'changes_exact3': "SELECT * FROM kifu_name_changes WHERE target_table='kifu_name_research_evidence' AND target_row_id IN (1208,1209,1207)",
 'changes_page19': "SELECT * FROM kifu_name_changes WHERE target_table='kifu_name_research_evidence' AND target_row_id IN (902,392,1032,917,927,942,817,1207,442,1112,862,222,617,367,1137,757,4477,377,1917)",
 'name_zero_match': "SELECT id FROM kifu_raw_event_names WHERE status='verified' AND (display_name='王星昊' OR lower(display_name)='王星昊')",
 'player_count': "SELECT count(id) FROM kifu_albums WHERE duplicate_of_id IS NULL AND list_hidden_reason IS NULL AND (black_player_id=25 OR white_player_id=25)",
}
with engine.connect() as c:
 tx=c.begin(); c.execute(text('SET TRANSACTION READ ONLY'));c.execute(text("SET LOCAL statement_timeout='3000ms'"));c.execute(text("SET LOCAL lock_timeout='500ms'"))
 for label,sql in queries.items():
  print(json.dumps(dict(label=label,explain=c.execute(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql)).scalar()),ensure_ascii=False,default=str),flush=True)
 print(json.dumps(dict(metadata=[dict(x) for x in c.execute(text("SELECT relname,n_live_tup,n_dead_tup,last_analyze,last_autoanalyze,pg_total_relation_size(relid) bytes FROM pg_stat_user_tables WHERE relname IN ('kifu_name_changes','kifu_name_batches','kifu_raw_event_names','kifu_player_names')")).mappings()]),default=str),flush=True)
 tx.rollback()
