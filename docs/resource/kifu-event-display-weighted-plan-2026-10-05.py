"""Produce weighted display candidates from read-only captures; no DB/translation-table access."""
from pathlib import Path
import gzip,hashlib,json,collections,re,unicodedata
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'kifu-event-display-weighted-plan-2026-10-05'
ENRICHED=ROOT/'kifu-sgf-event-supplemental-enriched-prod-2026-10-04.jsonl.gz'
SOURCES={
 'Castle Game':('御城碁','https://en.wikipedia.org/wiki/Oshirogo'),
 'Hoensha game':('方圆社对局','https://zh.wikipedia.org/wiki/方圓社'),
 'Nihon Ki-in #1':('日本棋院第一位决定战','https://zh.wikipedia.org/wiki/日本棋院第一位決定戰'),
 'Kiseong':('韩国棋圣战','https://goldengibo.baduk.or.kr/info/info_view.asp?cmpt_code=1108&cmpt_th=12&cmpt_tnmt_div=1'),
 '10-game match':('十番棋','https://gomagic.org/go-term/jubango/'),
 'Tokyo Shinbun Cup':('日本东京新闻杯','https://homepages.cwi.nl/~aeb/go/games/games/TokyoShinbun/index.html'),
}
def key(s):return re.sub(r'[^\w\u4e00-\u9fff]','',unicodedata.normalize('NFKC',s or '').casefold())
def chinese(s):return bool(re.search(r'[\u4e00-\u9fff]',s or ''))
def plausible(s):return chinese(s) and len(s or '')<=150 and not re.search(r'(?i)\.sgf|sgf$|结果:|黑胜|白胜|\d+手$',s) and bool(re.search(r'战|赛|杯|囲碁|围甲|围乙|围丙|擂台|大手合|御城|升段|团体|棋圣|运动会|全运会|智运会|积分大循环|军团|研究会|训练',s))
def clean(s):
 original=s.strip();s=original
 s=re.sub(r'^(?:(?:19|20)\d{2}年?\s*|第?[0-9一二三四五六七八九十]+[届期]\s*)+','',s)
 # Terminal edition/round/stage qualifiers only; country/gender/type words remain.
 suffix=r'(?:[0-9]+/[0-9]+轮|第?[0-9一二三四五六七八九十]+(?:轮|局|回战|回合|台)|\d+强(?:战|赛)?|预选(?:赛)?|本选(?:赛)?|循环圈(?:赛)?|循环赛|本赛|本战|半决赛|决赛|挑战赛|初赛(?:胜部|败部)?|败者复活赛|胜部|败部|五番棋|七番棋|[357]番棋)$'
 while True:
  new=re.sub(suffix,'',s).strip()
  if new==s:break
  s=new
 return s if plausible(s) else original
assert clean('2024年第3届韩国女子围棋联赛第1轮')=='韩国女子围棋联赛'
assert clean('2026世界围棋团体赛热身赛1/3轮')=='世界围棋团体赛热身赛'
assert not plausible('2007cn-duan-5-zhanglsgf')
sgf=[]
for line in gzip.open(ENRICHED,'rt',encoding='utf-8'):
 r=json.loads(line)
 if r.get('kind')=='album':sgf.append(r)
reports={};outputs=[]
for env in ['prod','test']:
 path=ROOT/f'kifu-event-display-weighted-{env}-capture-2026-10-04.json';cap=json.loads(path.read_text());events={r['id']:r['canonical_name'] for r in cap['events']};lookup=collections.defaultdict(set)
 for id_,name in events.items():lookup[key(name)].add(name)
 for a in cap['aliases']:lookup[key(a['alias'])].add(events[a['event_id']])
 # Established linked spelling variants are read-only evidence; preserve conflicts.
 for r in cap['raw_groups']:
  if r['event_id'] and r['core']:lookup[key(r['core'])].add(events[r['event_id']])
 plans=[];byraw={};tier=collections.Counter();display=collections.Counter();noncn=collections.Counter()
 for row in cap['raw_groups']:
  raw=row['raw'];core=row['core'];name=None;why=None;source=None;conflict=[]
  if row['event_id'] and chinese(events[row['event_id']]):name=clean(events[row['event_id']]);why='EXISTING_EVENT_ID_CHINESE'
  else:
   matches=set().union(*(lookup.get(key(v),set()) for v in [raw,core] if v))
   matches={clean(n) for n in matches if chinese(n)}
   if len(matches)==1:name=next(iter(matches));why='UNAMBIGUOUS_CATALOG_ALIAS_OR_LINKED_CORE'
   elif len(matches)>1:conflict=sorted(matches)
   if not name and not conflict:
    label=next((v for v in [core,raw] if plausible(v)),None)
    if label:name=clean(label);why='EXISTING_CHINESE_LABEL_CLEAN'
    elif core in SOURCES:name,source=SOURCES[core];why='RESEARCHED_EXACT_CORE_DISPLAY'
  if not name:why='HOLD_CATALOG_CONFLICT' if conflict else 'KEEP_ORIGINAL';noncn[core or raw]+=row['games']
  proposal=row|{'display_candidate':name,'candidate_kind':why,'source_url':source,'conflicting_candidates':conflict,'application_scope':'display_only; exact raw + captured event_id guard; retain original EV/event_id'}
  plans.append(proposal);tier[why]+=row['games']
  if name:display[name]+=row['games']
  if row['event_id'] is None:byraw[raw]=proposal
 # Supplemental labels are exact-album overrides only where base rule cannot yield Chinese display.
 overrides=[];holds=[]
 for r in sgf:
  base=byraw.get(r['album_event'])
  if not base or base['display_candidate']:continue
  vals=r['root_properties']['GN'][1:]+[c['value'] for c in r['candidates']]
  names={clean(re.sub(r'\s*\|\s*\d+手$','',v)) for v in vals if plausible(re.sub(r'\s*\|\s*\d+手$','',v))}
  if len(names)==1:
   name=next(iter(names));overrides.append({'album_id':r['album_id'],'exact_raw':r['album_event'],'exact_core':r['series_core'],'sgf_sha256':r['sgf_sha256'],'display_candidate':name,'root_GN':r['root_properties']['GN'],'root_GC':r['root_properties']['GC'],'candidate_kind':'SGF_EXACT_ALBUM_CHINESE_DISPLAY','approval':'PROPOSED_ONLY','original_EV_preserved':True});display[name]+=1
  elif len(names)>1:holds.append({'album_id':r['album_id'],'exact_raw':r['album_event'],'display_candidates':sorted(names),'reason':'SGF_CHINESE_LABELS_DISAGREE'})
 raw_states=collections.defaultdict(set)
 for r in cap['raw_groups']:raw_states[r['raw']].add(r['event_id'])
 assert all(raw_states[r['exact_raw']]=={None} for r in overrides), 'supplemental coverage requires unambiguous unlinked raw population'
 assert all(n<=byraw[raw]['games'] for raw,n in collections.Counter(r['exact_raw'] for r in overrides).items())
 remaining_by_core=noncn.copy()
 for r in overrides:remaining_by_core[r['exact_core'] or r['exact_raw']]-=1
 covered=sum(n for t,n in tier.items() if t not in ['KEEP_ORIGINAL','HOLD_CATALOG_CONFLICT'])+len(overrides)
 # Weighted minimal display-name set: distinct target labels by coverage, disjoint album accounting.
 cumulative=0;ranked=[]
 for name,n in display.most_common():
  cumulative+=n;ranked.append({'display_candidate':name,'games':n,'cumulative_games':cumulative,'fraction_all_games':round(cumulative/cap['totals']['games'],6)})
 thresholds={}
 for pct in [0.8,0.9,0.95]:
  hit=next((i+1 for i,r in enumerate(ranked) if r['fraction_all_games']>=pct),None);thresholds[str(pct)]=hit
 out=ROOT/f'kifu-event-display-weighted-{env}-candidates-2026-10-05.jsonl.gz'
 with out.open('wb') as rawout,gzip.GzipFile(filename='',fileobj=rawout,mode='wb',mtime=0) as f:
  for row in [{'kind':'manifest','environment':env,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'capture_meta':cap['meta'],'display_only':True}]+[{'kind':'raw_candidate'}|p for p in plans]+[{'kind':'album_override'}|r for r in overrides]+[{'kind':'album_hold'}|r for r in holds]:f.write((json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode())
 outputs.append(out)
 report={'totals':cap['totals'],'capture_elapsed_seconds':cap['elapsed_seconds'],'read_only':cap['meta']['read_only'],'capture_transaction_end':cap['transaction_end'],'tier_game_counts':dict(tier),'supplemental_exact_album_overrides':len(overrides),'supplemental_conflict_holds':len(holds),'retain_original_or_blank_games':cap['totals']['games']-covered,'retain_original_nonblank_games':cap['totals']['nonblank_event']-covered,'proposed_chinese_display_games':covered,'fraction_all_games':round(covered/cap['totals']['games'],6),'fraction_nonblank_events':round(covered/cap['totals']['nonblank_event'],6),'smallest_distinct_target_display_names_for_fraction_all_games':thresholds,'target_names_ranked':ranked,'unmapped_or_conflict_cores_top100':[{'core':v,'games_before_sgf_overrides':n} for v,n in noncn.most_common(100)],'remaining_original_cores_top100':[{'core':v,'games':n} for v,n in remaining_by_core.most_common(100) if n>0],'candidate_artifact':out.name,'candidate_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'raw_candidate_groups':len(plans),'approvals':0,'database_writes':0,'translation_table_writes':0}
 reports[env]=report
allreport={'format':'kifu-event-display-weighted-plan-v1','generated_date':'2026-10-05','purpose':'Chinese presentation coverage; no identity dedup/association approvals','source_sgf_artifact':ENRICHED.name,'source_sgf_sha256':hashlib.sha256(ENRICHED.read_bytes()).hexdigest(),'researched_core_display_candidates':[{'exact_core':k,'display_candidate':v[0],'source_url':v[1]} for k,v in SOURCES.items()],'environments':reports,'application_plan':['First use existing event_id -> Chinese catalog canonical, cleaned for display only.','For remaining labels use exact catalog aliases / established linked core only when one display target.','Clean already Chinese raw/core conservatively: remove leading year/edition and terminal stage/round only; preserve country, gender, event type.','Use researched exact non-Chinese core mappings for display, without creating identity aliases.','Apply supplementary GN/GC names as exact album_id + SGF SHA guarded display overrides; do not promote filename aliases.','On disagreement or unmapped text keep original event label; preserve original EV, date, round and all identity fields.','Use one versioned local display mapping artifact + optional per-album overrides consumed at read time; rollout TEST first and compare weighted totals, then PROD. No translation table migration needed.'],'limitations':['Contains proposed cleaning rules, not deployment approval.','Chinese presence is an explicitly measured presentation proxy, not independently verified event identity.','Enriched SGF artifact covers prior unclassified/unlinked population, not all current games; only still-unlinked raw groups considered for overrides.','Weighted threshold counts target display names, not reviewed identity cores or total exact raw mapping rows.','Existing dirty catalog names may need focused display review; no canonical/identity records are changed.']}
BASE.with_suffix('.json').write_text(json.dumps(allreport,ensure_ascii=False,indent=2)+'\n')
md=['# 赛事中文显示加权批量计划（只读候选）','','PROD与TEST分别读取全库聚合；不逐局考证身份。原始EV、年份、轮次、赛事ID保持原样，仅提出展示文字覆盖。所有候选未自动批准，写库/译表写入0。','','|环境|总局数|非空赛事|已有关联|拟中文显示覆盖|总局覆盖率|非空赛事覆盖率|SGF exact album补充|冲突HOLD|','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for env,r in reports.items():md.append(f'|{env.upper()}|{r["totals"]["games"]}|{r["totals"]["nonblank_event"]}|{r["totals"]["linked"]}|{r["proposed_chinese_display_games"]}|{r["fraction_all_games"]:.2%}|{r["fraction_nonblank_events"]:.2%}|{r["supplemental_exact_album_overrides"]}|{r["supplemental_conflict_holds"]}|')
md+=['','## 最小集合解释','','共同使用目录映射和清洗规则，避免人工处理15k core。按互不重叠棋局加权排序的目标显示名称数：']
for env,r in reports.items():md.append('- '+env.upper()+': '+json.dumps(r['smallest_distinct_target_display_names_for_fraction_all_games'],ensure_ascii=False)+'（null表示当前候选总覆盖达不到该比例）。这不是外部考证通过数，也不是映射raw行数。')
md+=['','## 批量应用顺序','']
md+=['- '+step for step in allreport['application_plan']]
md+=['','## 重点非中文 exact core 候选','','|core|中文显示候选|来源|','|---|---|---|']
for k,v in SOURCES.items():md.append('|'+k+'|'+v[0]+'|[来源]('+v[1]+')|')
md+=['','## 高频目标显示与覆盖（PROD前40）','','|显示候选|局数|累计总局覆盖|','|---|---:|---:|']
for r in reports['prod']['target_names_ranked'][:40]:md.append('|'+r['display_candidate']+'|'+str(r['games'])+'|'+f'{r["fraction_all_games"]:.2%}'+'|')
md+=['','## 保留原文/HOLD高频项（PROD，补SGF之后）','','剩余原文/缺EV的实际数量见JSON retain_original_nonblank_games / retain_original_or_blank_games。当前0个补充标签互相冲突并不表示没有未映射项。以下为exact album补充后的剩余分布。','','|core|局数|','|---|---:|']
for r in reports['prod']['remaining_original_cores_top100'][:25]:md.append('|'+str(r['core'])+'|'+str(r['games'])+'|')
md+=['','## Artifact与验证','','同目录`.py`可从两份capture JSON与enriched gzip复现。两个候选gzip逐raw保存来源/覆盖、逐album保存GN/GC与SGF SHA；冲突保留原文。两环境读取事务均READ ONLY、ROLLBACK，源查询不读取全库SGF、不加写锁。清洗规则与新增史料映射仍需快速抽样确认后应用。']
BASE.with_suffix('.md').write_text('\n'.join(md)+'\n');outputs.extend(BASE.with_suffix(s) for s in ['.py','.json','.md']);outputs.extend([ROOT/'kifu-event-display-weighted-capture-2026-10-05.py']+[ROOT/f'kifu-event-display-weighted-{env}-capture-2026-10-04.json' for env in ['prod','test']]);BASE.with_suffix('.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in outputs))
print(json.dumps({env:{k:v for k,v in r.items() if k not in ['target_names_ranked','unmapped_or_conflict_cores_top100','remaining_original_cores_top100']} for env,r in reports.items()},ensure_ascii=False))
