"""Local read-only classification of three captured exact SGF event cores."""
from pathlib import Path
import collections,gzip,hashlib,json,re
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'kifu-sgf-event-supplemental-enriched-prod-2026-10-04.jsonl.gz'
BASE=ROOT/'kifu-sgf-event-highfrequency-families-prod-2026-10-04'
CORES=['团体赛','中日围棋友谊赛','Kiseong']
SOURCES=[
 {'id':'kba_kiseong','url':'https://goldengibo.baduk.or.kr/info/info_view.asp?cmpt_code=1108&cmpt_th=12&cmpt_tnmt_div=1','authority':'韩国棋院官方历史棋谱库','supports':'기성전真实独立赛事；1/2/3/4/5/6/7/8/10/11/12期对应1989/1990/1991/1992/1993/1994/1995/1996/1998/1999/2000；网页未列9与13，不推定不存在'},
 {'id':'nihonkiin_history','url':'https://www.nihonkiin.or.jp/profile/enkaku/','authority':'日本棋院官方沿革','supports':'1960日本代表团访中、1962中国代表团访日；未给SGF的统一届次体系'},
 {'id':'nihonkiin_exchange','url':'https://archive.nihonkiin.or.jp/igodendou/list09.html','authority':'日本棋院围棋殿堂陈毅史料','supports':'1960正式访中团及此后多次日中围棋交流；不是全部交流局的单一编号赛事表'},
 {'id':'cn_jp_history','url':'https://sports.sohu.com/2004/03/17/43/news219464383.shtml','authority':'专业体育媒体中国围棋年谱','supports':'1973/1974/1975等双方代表团交流史，不能直接核准所有届次/逐局'},
 {'id':'team1989','url':'https://sports.sina.cn/others/qipai/2022-06-03/detail-imizmscu4905355.d.html','authority':'围棋史料研究者冯斌据年鉴/专业刊物整理，新浪刊载','supports':'1989全国围棋团体赛4月10–23日武汉'},
 {'id':'team1992','url':'https://www.foxwq.com/news/mlist/id/13132.html','authority':'专业围棋平台刊载冯斌年鉴史料研究','supports':'1992全国围棋团体赛5月8–21日重庆；甲乙级/男女组分别存在'},
 {'id':'team1995','url':'https://foxwq.com/news/listid/id/13244.html','authority':'专业围棋平台刊载冯斌史料研究','supports':'1995全国围棋锦标赛团体5月12–25日漳州；原文承认部分资料未齐'},
 {'id':'team1997','url':'https://foxwq.com/news/listid/id/13293.html','authority':'专业围棋平台刊载冯斌据围棋天地/围棋年鉴整理','supports':'1997帝威斯杯全国围棋团体赛4月20–5月3日新都'},
 {'id':'team1998','url':'https://foxwq.com/news/listid/id/9931.html','authority':'专业围棋平台赛事历史研究','supports':'1998全国围棋团体赛4月15–28日杭州；与1999起围甲联赛分开'},
]
WINDOWS={1989:('1989-04-10','1989-04-23'),1992:('1992-05-08','1992-05-21'),1995:('1995-05-12','1995-05-25'),1997:('1997-04-20','1997-05-03'),1998:('1998-04-15','1998-04-28')}
OFFICIAL_K={1:1989,2:1990,3:1991,4:1992,5:1993,6:1994,7:1995,8:1996,10:1998,11:1999,12:2000}
CN={'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'十一':11,'十二':12,'十三':13,'二十二':22}
def num(s):return int(s) if s.isdigit() else CN.get(s)
def components(label):
 y=re.search(r'(?<!\d)((?:19|20)\d{2})',label)
 e=re.search(r'第([\d一二三四五六七八九十]+)[届期]',label) or re.search(r'(\d+)(?:st|nd|rd|th)',re.sub(r'^(?:19|20)\d{2}(?=\d)', '', label))
 r=re.search(r'第([\d一二三四五六七八九十]+)轮',label)
 g=re.search(r'第([\d一二三四五六七八九十]+)局',label)
 stage=[s for s in ['预选决赛','第一阶段','第二阶段','循环圈','半决赛','挑战赛','决赛','快棋表演赛'] if s in label]
 return {'label_year':int(y[1]) if y else None,'edition':num(e[1]) if e else None,'round':num(r[1]) if r else None,'game_index':num(g[1]) if g else None,'stage_terms':stage,'edition_text':e[0] if e else None,'group_text':(re.search(r'[一二三四五六七八九十\d]+组',label)[0] if re.search(r'[一二三四五六七八九十\d]+组',label) else None)}
rows=[];manifest=None
for line in gzip.open(SOURCE,'rt',encoding='utf-8'):
 r=json.loads(line)
 if r['kind']=='manifest':manifest=r
 if r.get('kind')!='album' or r['series_core'] not in CORES:continue
 p=r['root_properties'];label=p['GN'][-1] if p['GN'] else r['album_event'];c=components(label); rawc=components(r['album_event'])
 dates=p['DT'];dy=int(dates[0][:4]) if dates and re.match(r'^\d{4}',dates[0]) else None
 issues=[];notes=[];sources=[];type_candidate=None;target=None;status='TYPE_CANDIDATE';edition_year=None;season_status='SGF_ONLY'
 if len(dates)!=1 or dy==1900:issues.append('DATE_MISSING_OR_PLACEHOLDER')
 if c['label_year'] and dy and c['label_year']!=dy:issues.append('LABEL_YEAR_DT_DIFFER')
 for f in ['edition','round','game_index']:
  if rawc[f] and c[f] and rawc[f]!=c[f]:issues.append('RAW_GN_'+f.upper()+'_DIFFER')
 gc=[re.split(r'\s*\|\s*(?:结果|result)\s*:',s,maxsplit=1)[0].strip() for s in p['GC']]
 gc=[re.sub(r'\s*\|\s*\d+手$','',s) for s in gc]
 if gc and any(s!=label for s in gc):issues.append('GN_GC_TEXT_DIFFER')
 if r['series_core']=='Kiseong':
  type_candidate='韩国棋圣战';sources=['kba_kiseong'];edition_year=OFFICIAL_K.get(c['edition']);season_status='OFFICIAL_EDITION_YEAR' if edition_year else 'EDITION_YEAR_SOURCE_GAP'
  if edition_year and dy and dy!=edition_year:notes.append('CROSS_YEAR_EDITION_REVIEW;日期与官方期别年份不同，不能自动判错或改届次')
  if c['edition'] in (9,13):notes.append('官方所读历史页未列此期；SGF届次保留，另查完整赛事史')
 elif r['series_core']=='团体赛':
  if label=='团体赛半决赛':status='HOLD_TYPE_UNCLEAR';issues.append('GENERIC_TEAM_SEMIFINAL_AND_1900_DATE')
  else:
   type_candidate='中国全国围棋团体赛';target=73;year=c['label_year'] or dy;edition_year=year
   if year in WINDOWS:
    sources=['team'+str(year)];season_status='PROFESSIONAL_HISTORY_YEAR_WINDOW'
    if not dates or not WINDOWS[year][0]<=dates[0]<=WINDOWS[year][1]:issues.append('DATE_OUTSIDE_HISTORY_WINDOW')
   else:notes.append('赛事类型候选保留；本轮未核实该年赛事日程或第11期编号')
   if not ('全国围棋' in label):notes.append('GN仍是年份+团体赛泛称；类型归属由同年中国棋手/时间簇推断，不能建立泛称别名')
 else:
  sources=['nihonkiin_history','nihonkiin_exchange','cn_jp_history'];edition_year=c['label_year'] or dy
  if '神户新闻业余访华团' in label:
   type_candidate=label;status='HOLD_SEPARATE_VISIT';issues.append('AMATEUR_VISIT_NOT_NATIONAL_NUMBERED_EVENT')
  elif '团中日围棋交流赛' in label:
   type_candidate='中日围棋交流赛';status='TYPE_CANDIDATE_SEPARATE_DELEGATION';notes.append('按原GN访华团名分组，不能并入同年编号对抗赛')
  elif '中日围棋对抗赛' in label:
   type_candidate='中日围棋对抗赛';target=75;notes.append('raw友谊赛与GN对抗赛名称变体；保留对抗赛序列，不能沿用友谊赛届次')
  else:
   type_candidate='中日围棋友谊赛' if '友谊赛' in label else '中日围棋交流赛';notes.append('友谊/交流类型候选有史料支撑；与catalog75的类型归并需政策决策')
  season_status='SGF_YEAR_EDITION_UNVERIFIED';notes.append('届次仅来自GN；1965年第6/7/8届与1966年第10届不可按年序推届次')
 rows.append({'album_id':r['album_id'],'raw_event_id':r['raw_event_id'],'exact_raw':r['album_event'],'exact_core':r['series_core'],'source_path':r['source_path'],'sgf_sha256':r['sgf_sha256'],'root_properties':p,'selected_GN_label':label,'components':c,'raw_components':rawc,'game_date_year':dy,'edition_year_candidate':edition_year,'year_evidence_status':season_status,'type_candidate_zh':type_candidate,'existing_type_id_candidate':target,'type_evidence_status':status,'metadata_issues':issues,'notes':notes,'source_ids':sources,'pairing_verified_externally':False,'approval_status':'AWAITING_ASTRA_POLICY','supplemental_diff_extracted':bool(r['candidates']),'original_supplemental_candidates':r['candidates']})
rows.sort(key=lambda r:r['album_id'])
groups=collections.defaultdict(list)
for r in rows:
 c=r['components'];group=(r['exact_core'],r['type_candidate_zh'],r['edition_year_candidate'],c['edition'],c['round'],c['game_index'],tuple(c['stage_terms']),c['group_text'],r['selected_GN_label'] if r['type_evidence_status']=='TYPE_CANDIDATE_SEPARATE_DELEGATION' else '')
 groups[group].append(r['album_id'])
coverage=[]
for core in CORES:
 rs=[r for r in rows if r['exact_core']==core]
 coverage.append({'exact_core':core,'games':len(rs),'supplemental_diff_games':sum(r['supplemental_diff_extracted'] for r in rs),'multiple_GN_games':sum(len(r['root_properties']['GN'])>1 for r in rs),'edition_known_from_GN_games':sum(r['components']['edition'] is not None for r in rs),'type_candidate_games':sum(r['type_candidate_zh'] is not None for r in rs),'type_evidence_status':dict(collections.Counter(r['type_evidence_status'] for r in rs)),'cross_year_edition_review_games':sum(any(n.startswith('CROSS_YEAR_EDITION_REVIEW') for n in r['notes']) for r in rs),'metadata_issue_games':sum(bool(r['metadata_issues']) for r in rs),'issues':dict(collections.Counter(i for r in rs for i in r['metadata_issues'])),'year_evidence_status':dict(collections.Counter(r['year_evidence_status'] for r in rs))})
report={'format':'kifu-event-highfrequency-readonly-v1','source_artifact':SOURCE.name,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'source_manifest':manifest,'exact_core_filter':CORES,'counts':{'games':len(rows),'exact_cores':3,'groups':len(groups),'database_writes':0,'translations':0,'approvals':0},'coverage':coverage,'sources':SOURCES,'catalog_readonly_check':{'sql':"SELECT id,canonical_name FROM kifu_events WHERE canonical_name LIKE '%团体%' OR canonical_name LIKE '%中日%' OR canonical_name LIKE '%棋圣%' OR canonical_name='Kiseong' ORDER BY id",'read_only':'on','transaction_end':'ROLLBACK','relevant_types':{'73':'中国全国围棋团体赛','75':'中日围棋对抗赛'},'korean_kiseong_found':False},'policy_boundary':'No automatic approval or rejection. Missing per-game independent pairing evidence does not remove an independently supported event-type candidate. Astra decides approval scope. Date/edition and type evidence are separate.','groups':[{'exact_core':k[0],'type_candidate_zh':k[1],'edition_year_candidate':k[2],'edition':k[3],'round':k[4],'game_index':k[5],'stage_terms':list(k[6]),'group_text':k[7],'delegation_label':k[8],'games':len(ids),'exact_album_ids':ids} for k,ids in sorted(groups.items(),key=lambda item:str(item[0]))],'albums':rows}
assert components('200113thKiseong')['edition']==13
assert components('第2届韩国棋圣战循环圈第22局')['round'] is None
assert components('第2届韩国棋圣战循环圈第22局')['game_index']==22
assert len(rows)==646 and len({r['album_id'] for r in rows})==646
BASE.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
md=['# 高频赛事 core 的GN/GC补充预处理（只读）','','## 范围与覆盖','','捕获artifact内3个exact core，共646局，均保留精确album IDs、原raw/core、GN/GC/DT/RO及SGF SHA。类型候选、届次年份和棋局归属分开记录。未核准逐局外部配对不会删除已具赛事史料支撑的类型候选；批准范围待Astra政策决策，批准/写库/翻译均0。','','|exact core|局数|新增差异GN/GC覆盖|GN可读届次|类型候选|有元数据问题|','|---|---:|---:|---:|---:|---:|']
for c in coverage:md.append('|'+c['exact_core']+'|'+str(c['games'])+'|'+str(c['supplemental_diff_games'])+'|'+str(c['edition_known_from_GN_games'])+'|'+str(c['type_candidate_games'])+'|'+str(c['metadata_issue_games'])+'|')
md+=['','## 类型与分组结论','','- Kiseong：韩国棋院官方历史库证明기성전独立赛事，提出“韩国棋圣战”类型候选；catalog本轮未发现此类型。152局全部GN可读届次，29局具有与raw不同的补充内容；重复GN的123局仍可用于届次归并。官方页缺9/13期，不据此丢弃其候选。跨年决赛日期与期别年份分列，循环圈“第22局”是局序，不能当第22轮。','- 团体赛：323局提出“中国全国围棋团体赛”(id=73)候选，其中多数GN仍仅年份+泛称，需保留推断证据等级。1989/1992/1995/1997/1998有专业史料日程可比较；1996等年份仍待查日程。1局1900日期、GN仅“团体赛半决赛”保持类型不明。第11期1977的阶段/组别按原文保留，不按年份自动推届次。','- 中日友谊赛：170局不可单一届次序列归并。保留1960年代友谊赛、1973以后GN明确对抗赛的序列、1978不同访华团以及神户新闻业余团。官方史料证明多次互访交流；具体届次暂仅SGF支持。id=75仅为GN明确对抗赛候选的既有类型参照，友谊/交流与75是否同类型待政策决定。','','## 内部问题与证据界限','','GN与GC同源，重复不算独立证据；RO为空时不造轮次；年份与DT比较只作问题提示。届次跨年不自动判错；类型候选不会因缺逐局外证而直接终止。各条issue、notes及最终政策状态在JSON。','','## 来源','']
for s in SOURCES:md.append('- ['+s['id']+']('+s['url']+')：'+s['authority']+'；'+s['supports']+'。')
md+=['','## 可复现与精确范围','','运行同目录`.py`仅读取本地已捕获gzip并生成报告。精确过滤 `series_core IN (团体赛, 中日围棋友谊赛, Kiseong)`，不建立泛称别名，不更新数据库。源SHA：`'+report['source_sha256']+'`。完整646个exact album见JSON；以下按类型、期别/年、轮次/局序分组列出。','','|core|类型候选|年/届/轮/局|阶段/组/访华团|局数|exact album IDs|','|---|---|---|---|---:|---|']
for g in report['groups']:
 md.append('|'+g['exact_core']+'|'+str(g['type_candidate_zh'])+'|'+'/'.join(str(g[x]) for x in ['edition_year_candidate','edition','round','game_index'])+'|'+' '.join(g['stage_terms']+[g['group_text'] or '',g['delegation_label']])+'|'+str(g['games'])+'|'+','.join(map(str,g['exact_album_ids']))+'|')
BASE.with_suffix('.md').write_text('\n'.join(md)+'\n')
BASE.with_suffix('.sha256').write_text(''.join(hashlib.sha256(BASE.with_suffix(ext).read_bytes()).hexdigest()+'  '+BASE.with_suffix(ext).name+'\n' for ext in ['.py','.json','.md']))
print(json.dumps({'counts':report['counts'],'coverage':coverage},ensure_ascii=False))
