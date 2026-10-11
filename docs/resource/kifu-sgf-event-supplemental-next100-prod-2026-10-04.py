"""Reproduce exact scope selection from captured SGF artifact; local files only."""
from pathlib import Path
import collections, gzip, hashlib, json, re

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'kifu-sgf-event-supplemental-enriched-prod-2026-10-04.jsonl.gz'
BASE = ROOT / 'kifu-sgf-event-supplemental-next100-prod-2026-10-04'
SEED = 'kifu-event-gn-gc-next100-2026-10-04-v1'
DATES = {n: '2007-07-' + day for n, day in enumerate(['11','12','13','15','16','17','19','20','21','23','24','25'],1)}
SOURCES = [
 {'id':'rank_schedule','url':'https://sports.sina.com.cn/go/2007-06-29/10373008597.shtml','authority':'当年专业赛事报道及组委会补充通知','supports':'2007 武汉段位赛、定段/升段分组、升段赛12轮及轮次日期；不支持所有逐局配对'},
 {'id':'league_organizer','url':'https://www.newswire.co.kr/newsRead.php?no=25989','authority':'BadukTV 原发布方赛事总结新闻稿','supports':'2004 한국바둑리그赛事类型与赛季；不支持全部逐局配对'},
 {'id':'league_final','url':'https://sports.sina.com.cn/o/2005-01-03/11561331284.shtml','authority':'当年专业赛事报道','supports':'2004赛季延续至2005年1月2日；不能按DT年份重命名赛季'},
]
prior=json.loads((ROOT / 'kifu-event-longtail-review-2026-10-04.json').read_text())
prior_ids={r['album_id'] for r in prior['rows']}
rows=[]; manifest=None
for line in gzip.open(SOURCE,'rt',encoding='utf-8'):
 row=json.loads(line)
 if row['kind']=='manifest':manifest=row
 if row['kind']=='album':rows.append(row)
league=collections.defaultdict(list); rank=collections.defaultdict(list); pool=[]
for row in rows:
 if row['album_id'] in prior_ids:continue
 vals=[c['value'] for c in row['candidates']]
 if '2004年韩国围棋联赛' in vals:league[row['series_core']].append(row)
 if any('2007' in v and '段位' in v for v in vals):pool.append(row)
 match=re.fullmatch(r'2007cn-duan-(\d+)-.*',row['series_core'])
 if match and any(v.startswith('2007年中国围棋段位赛') for v in vals):rank[int(match[1])].append(row)
key=lambda r:hashlib.sha256((SEED+'|'+r['series_core']).encode()).hexdigest()
selected=[]
for n in range(1,13):selected.extend(sorted(rank[n],key=key)[:4])
used={r['album_id'] for r in selected}
selected.extend(sorted((r for group in rank.values() for r in group if r['album_id'] not in used),key=key)[:4])
scopes=[]
for family, groups in [('league2004',league),('rank2007',{r['series_core']:[r] for r in selected})]:
 for core, games in sorted(groups.items()):
  hold=[]; proposals=[]
  for row in games:
   p=row['root_properties']; n=int(re.fullmatch(r'2007cn-duan-(\d+)-.*',core)[1]) if family=='rank2007' else None
   if any('半决赛' in c['value'] for c in row['candidates']):hold.append('GN/GC半决赛与升段12轮赛程语义不符；阶段不归并')
   if n and p['DT']!=[DATES[n]]:hold.append('SGF日期与升段赛程轮次日期不一致')
   if family=='league2004' and (not p['DT'] or not ('2004-05-13' <= p['DT'][0] <= '2005-01-02')):hold.append('日期超出已知2004赛季窗口或缺失')
   proposals.append({'album_id':row['album_id'],'raw_event_id':row['raw_event_id'],'exact_raw':row['album_event'],'source_path':row['source_path'],'sgf_sha256':row['sgf_sha256'],'root_properties':p,'supplemental_candidates':row['candidates'],'round_candidate':n,'expected_round_date':DATES.get(n),'pairing_verified':False})
  scopes.append({'exact_core':core,'family':family,'associated_games':len(games),'type_candidate':'韩国围棋联赛' if family=='league2004' else '中国围棋段位赛','existing_type_id':50 if family=='league2004' else None,'season_year_candidate':2004 if family=='league2004' else 2007,'edition_number':None,'stage_candidate':None if family=='league2004' else '升段组待核准','round_candidate':None if family=='league2004' else proposals[0]['round_candidate'],'candidate_status':'HOLD_METADATA_CONFLICT' if hold else 'CANDIDATE_REVIEW','final_association_status':'HOLD_UNVERIFIED_PAIRING','hold_reasons':sorted(set(hold)),'source_ids':['league_organizer','league_final'] if family=='league2004' else ['rank_schedule'],'games':proposals})
counts=collections.Counter(s['candidate_status'] for s in scopes)
report={'format':'kifu-event-supplemental-next100-v1','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_artifact':SOURCE.name,'source_manifest':manifest,'selection':{'seed':SEED,'ordering':'sha256(UTF8(seed + "|" + exact_core)) ascending','scope':'Excluding30 pilot album IDs; all48 exact cores containing exact candidate 2004年韩国围棋联赛 (50 albums); for filename-shaped2007cn-duan-N-* cores with supplementary2007年中国围棋段位赛 select4perround1..12 then4remaining by global hash','scope_is_captured_snapshot':True,'excluded_prior_album_ids':sorted(prior_ids),'excluded_prior_artifact':'kifu-event-longtail-review-2026-10-04.json'},'source_urls':SOURCES,'catalog_readonly_check':{'date':'2026-10-04','existing_type':{'id':50,'canonical_name':'韩国围棋联赛'},'rank_type_found':False,'sql':"SELECT id, canonical_name FROM kifu_events WHERE canonical_name LIKE '%段位%' OR canonical_name LIKE '%韩国%联赛%' ORDER BY id",'transaction_read_only':'on','transaction_end':'ROLLBACK'},'counts':{'exact_cores':len(scopes),'associated_games':sum(s['associated_games'] for s in scopes),'candidate_status':dict(counts),'final_hold_cores':len(scopes),'approved':0,'database_writes':0,'translations':0},'extension_pool':{'rank2007_distinct_albums':sum(any('2007' in c['value'] and '段位' in c['value'] for c in r['candidates']) for r in rows),'rank2007_round5_semifinal_label_games':sum(any('第五轮半决赛' in c['value'] for c in r['candidates']) for r in rows),'rank2007_schedule_date_conflict_album_ids':[r['album_id'] for n,g in rank.items() for r in g if r['root_properties']['DT']!=[DATES[n]]],'league2004_semifinal_extra_album_ids':[r['album_id'] for r in rows if any(c['value']=='2004年韩国围棋联赛半决赛' for c in r['candidates'])]},'limitations':['GN and GC are correlated imported SGF metadata, not two independent sources.','Event sources verify type/year/schedule, not every captured SGF game. No association approval is made.','Same exact core may contain multiple albums: approvals must use listed album IDs and source hashes, never broad alias matching.','Rank2007 generic event type does not establish定段vs升段 or edition27.','No deduplication: multi-album cores remain separate games.'],'scopes':scopes}
assert len(scopes)==100 and sum(s['associated_games'] for s in scopes)==102
assert len({g['album_id'] for s in scopes for g in s['games']})==102
assert not prior_ids.intersection(g['album_id'] for s in scopes for g in s['games'])
BASE.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
lines=['# GN/GC 补充赛事下一批100个 exact core（只读候选）','','## 范围与结论','','基于已捕获生产快照选定100个 exact core、102局：2004韩国联赛48 core/50局；2007段位赛52 core/52局（已排除原30样本）。赛事类型与赛季可参考下列专业来源；本批逐局外部配对未核准，所有关联最终保持 HOLD，不产生批准、写库或翻译。','','初步候选分类：'+json.dumps(dict(counts),ensure_ascii=False)+'。CANDIDATE_REVIEW仅表示没有发现当前日期/阶段冲突，不等于SAFE。','','韩国联赛已有赛事类型id=50；只读查询未发现含“段位”的类型。2004赛季可跨至2005年1月2日；届次数字留空。2007按轮次、日期提出升段组候选，定段组与升段组不可仅凭统称合并，届次数字留空。','','## 来源及证据边界','']
for s in SOURCES:lines.append(f'- [{s["id"]}]({s["url"]})：{s["authority"]}；{s["supports"]}。')
lines+=['','## 可复现选择','','固定seed：`'+SEED+'`；2004精确同名候选排除原30样本后全取48core；2007文件形core按12轮每轮取hash最小4个，再取剩余全局hash最小4个。运行同目录`.py`可从本地gzip复现JSON/MD/SHA，不连接生产。输入SHA256：`'+report['source_sha256']+'`。范围绑定原捕获快照，后续处理应按album_id、exact raw/core、SGF SHA再核对。','','## 后续扩展及冲突','','2007补充候选池共'+str(report['extension_pool']['rank2007_distinct_albums'])+'局，其中“第五轮半决赛”70局需单列HOLD：不能把半决赛当类型的一部分，也不能自动删除。升段赛程日期不符：album_id '+str(report['extension_pool']['rank2007_schedule_date_conflict_album_ids'])+'。2004另外3个明确半决赛候选不在本批，IDs '+str(report['extension_pool']['league2004_semifinal_extra_album_ids'])+'；应分别核实阶段与对阵。','','下一步按轮次赛果表补逐局棋手对阵，再用原SGF核对颜色、结果和职业段位；韩国先补球队/台次/常规赛或季后赛。GN/GC同源，不能重复计为两份外证。保留100个exact范围逐条决策，禁止创建覆盖整个文件名族的自动别名。','','## 精确范围清单','','完整原GN/GC、日期、对阵、原始路径及SHA在同名JSON。','','|exact core|局数|album IDs|类型/赛季/轮次候选|候选分类|','|---|---:|---|---|---|']
for s in scopes:lines.append('|'+s['exact_core']+'|'+str(s['associated_games'])+'|'+','.join(str(g['album_id']) for g in s['games'])+'|'+s['type_candidate']+'/'+str(s['season_year_candidate'])+'/'+str(s['round_candidate'])+'|'+s['candidate_status']+'|')
BASE.with_suffix('.md').write_text('\n'.join(lines)+'\n')
paths=[BASE.with_suffix(s) for s in ('.py','.json','.md')]
BASE.with_suffix('.sha256').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in paths))
print(json.dumps(report['counts'],ensure_ascii=False))
