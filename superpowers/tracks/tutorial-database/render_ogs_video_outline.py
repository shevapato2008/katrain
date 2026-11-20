"""Render the reviewed source locations as a self-contained local HTML outline."""
from collections import Counter
from html import escape
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DOCS = ROOT
BASE = 'ogs-video-outline-2026-11-12'
data = json.loads((DOCS / (BASE + '.json')).read_text())
units = data['source_units']
lessons = data['lessons']


def esc(value):
    return escape(str(value), quote=True)


def pdf_link(path, page=1):
    return esc(Path(path).as_uri() + '#page=' + str(page))


def bar(label, done, total, tone):
    pct=100*done/total if total else 0
    text=f'{pct:.1f}% · {done}/{total}' if total else '未定数量'
    return (f'<div class="meter {tone}"><div><span>{esc(label)}</span><strong>{text}</strong></div>'
            f'<progress max="{total or 1}" value="{done}" aria-label="{esc(label)}：{esc(text)}"></progress></div>')


def progress_cell(row):
    progress=row.get('media_progress')
    if not progress:return '<td class="production-progress">待同步进度</td>'
    c=progress['primary'];n=c['total']
    bars=bar('音频',c['audio'],n,'audio')+bar('Galaxy 4K',c['galaxy'],n,'galaxy')+bar('kiosk',c['kiosk'],n,'kiosk')
    supplement=progress['supplementary']
    extras=(f'<details class="supplement"><summary>补充素材 · {supplement["dual"]}/{supplement["total"]}图双档</summary>'
            +bar('补充音频',supplement['audio'],supplement['total'],'audio')
            +bar('补充4K',supplement['galaxy'],supplement['total'],'galaxy')
            +bar('补充kiosk',supplement['kiosk'],supplement['total'],'kiosk')+'</details>') if supplement['total'] else ''
    pending=(f'<p class="pending-note">{c["pending_static_confirmation"]}图未登记人工审核；本轮按用户生成授权制作。</p>'
             if c['pending_static_confirmation'] else '')
    return (f'<td class="production-progress"><strong class="production-stage">{esc(progress["stage"])}</strong>'
            f'<p class="progress-basis">主讲候选素材 · {n}图</p>{bars}{pending}{extras}'
            f'<p class="ogs-stage">OGS小节：{esc(progress["ogs_stage"])}</p></td>')


def source_item(key):
    s = units[key]
    start, end = s['pdf_pages']
    page = str(start) if start == end else f'{start}–{end}'
    section = ' / ' + s['section'] if s['section'] else ''
    extras = []
    if end > 50:
        extras.append('<span class="range-note">含PDF50页以后素材</span>')
    first = s['first_figure']
    if first:
        url = ('http://127.0.0.1:18012/admin?book=' + str(first['book_id'])
               + '&page=' + str(first['page']) + '&figure=' + str(first['figure_id']) + '&filter=all')
        extras.append(f'<a href="{esc(url)}" target="_blank" rel="noopener">测试后台棋图 ↗</a>')
    else:
        extras.append('<span>文字取材页</span>')
    if s['existing_related_videos']:
        extras.append(f'<span>含{s["existing_related_videos"]}段已有视频可参考，需重新编排</span>')
    note = f'<p class="selection-note">{esc(s["selection_note"])}</p>' if s['selection_note'] else ''
    return (f'<div class="source-item"><a class="book-title" href="{pdf_link(s["pdf"], start)}" '
            f'target="_blank" rel="noopener">《{esc(s["book_title"])}》 ↗</a>'
            f'<p>{esc(s["chapter"] + section)} · <strong>PDF {page}</strong></p>{note}'
            f'<div class="source-extra">{" · ".join(extras)}</div></div>')


status_cls = {'直接对应': 'direct', '跨章组合': 'combined', '需改编': 'adapt', '需补充': 'gap'}
table_rows = []
summary_rows = []
for chapter in data['chapters']:
    group = [r for r in lessons if r['chapter_id'] == chapter['id']]
    n = chapter['number']
    num_steps = sum(r['step_count'] for r in group)
    statuses = Counter(r['mapping_status'] for r in group)
    summary_rows.append(
        f'<tr><th scope="row"><a href="#chapter-{n}" data-chapter-link="{n}">{n:02} {esc(chapter["title"])}</a></th>'
        f'<td>{len(group)}</td><td>{num_steps:,}</td>'
        f'<td>{statuses["直接对应"]}直接 / {statuses["跨章组合"]}组合 / {statuses["需改编"]}改编 / {statuses["需补充"]}补充</td></tr>')
    table_rows.append(f'<tr class="chapter-row" id="chapter-{n}" data-heading="{n}"><th colspan="6" scope="colgroup">'
                      f'<span>第{n}章</span> {esc(chapter["title"])} <small>{len(group)}小节 · {num_steps:,}练习步骤</small></th></tr>')
    for row in group:
        keys = row['primary_sources'] + row['supplementary_sources']
        search = ' '.join(str(row[k]) for k in ('course_code', 'title', 'subtext', 'route', 'learning_goal'))
        for key in keys:
            s = units[key]
            search += ' ' + ' '.join(str(s[k]) for k in ('book_title', 'chapter', 'section', 'selection_note'))
            search += ' ' + ' '.join(map(str, s['pdf_pages']))
        primary = ''.join(source_item(k) for k in row['primary_sources'])
        extra = ''
        if row['supplementary_sources']:
            extra = (f'<details class="supplement"><summary>补充取材 · {len(row["supplementary_sources"])}段</summary>'
                     + ''.join(source_item(k) for k in row['supplementary_sources']) + '</details>')
        cls = status_cls[row['mapping_status']]
        anchor = row['course_code'].replace('.', '-')
        sub = f'<p class="subtext">{esc(row["subtext"])}</p>' if row['subtext'] else ''
        table_rows.append(
            f'<tr class="lesson-row" id="lesson-{anchor}" data-chapter="{n}" data-status="{esc(row["mapping_status"])}" data-search="{esc(search.lower())}">'
            f'<th scope="row"><span class="course-code">{esc(row["course_code"])}</span><h3>{esc(row["title"])}</h3>{sub}'
            f'<a class="ogs-link" href="{esc(row["source_url"])}" target="_blank" rel="noopener">OGS原小节 ↗</a></th>'
            f'<td class="goal">{esc(row["learning_goal"])}</td><td class="sources">{primary}{extra}</td>'
            f'<td><span class="badge {cls}">{esc(row["mapping_status"])}</span><p class="prep-note">候选页段已定位<br>具体例图待选</p></td>'
            f'<td class="steps"><strong>{row["step_count"]}</strong><span>原练习步骤</span><small>先看视频<br>再做本节练习</small></td>'
            +progress_cell(row)+'</tr>')

book_rows = []
for b in sorted(data['books'], key=lambda b: (-bool(b['reference_count']), -b['reference_count'])):
    state = f'本轮选用 · {b["reference_count"]}次来源引用' if b['reference_count'] else '保留，暂不进入本轮入门/初级主线'
    book_rows.append(f'<tr><th scope="row"><a href="{pdf_link(b["pdf"])}" target="_blank" rel="noopener">《{esc(b["title"])}》 ↗</a></th>'
                     f'<td>{b["pdf_pages"]}</td><td>{esc(state)}</td></tr>')

gaps = []
for r in lessons:
    if r['mapping_status'] == '需补充':
        gaps.append(f'<li><a href="#lesson-{r["course_code"].replace(".", "-")}" data-lesson-link="{r["course_code"].replace(".", "-")}">{esc(r["course_code"])} {esc(r["title"])}'
                    f'{(" · " + esc(r["subtext"])) if r["subtext"] else ""}</a><p>{esc(r["learning_goal"])}</p></li>')

chapter_options = ''.join(f'<option value="{c["number"]}">第{c["number"]}章 · {esc(c["title"])}</option>' for c in data['chapters'])
status_options = ''.join(f'<option>{esc(s)}</option>' for s in status_cls)
source = data['source']
provenance = esc(json.dumps(source, ensure_ascii=False, indent=2))
runtime=data.get('media_progress')
overall=''
if runtime:
    c=runtime['overall'];n=c['total']
    paused=runtime.get('status')=='paused'
    finished=runtime.get('status')=='completed_with_source_exclusions'
    production_note=('已按用户要求完成当前图后暂停，不自动续图或补洞；非实体及实际来源问题仍保留在整体分母中。'
                     if paused else '可制作素材已完成，来源问题已单列，当前没有生成任务运行。' if finished else '已按用户授权继续制作，不再以缺人工审核记录阻断；非实体及实际来源问题单列，仍保留在整体分母中。')
    refresh_note=('本轮已收口，文档按阶段同步更新。' if finished else '这是暂停后的最终快照，不再自动刷新制作进度。' if paused else '文件每45秒更新；浏览器保留当前页面，请刷新查看最新值。')
    stamp=datetime.fromisoformat(runtime['updated_at']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')
    cards=''.join('<div class="overall-card">'+bar(label,c[key],n,tone)+'</div>' for label,key,tone in [('音频','audio','audio'),('Galaxy 4K视频','galaxy','galaxy'),('kiosk视频','kiosk','kiosk')])
    admitted=runtime.get('user_authorized_scope') or runtime.get('approved_scope')
    approved_summary=''
    if admitted:
        approved_cards=''.join('<div class="overall-card">'+bar(label,admitted[key],admitted['total'],tone)+'</div>' for label,key,tone in [('音频','audio','audio'),('Galaxy 4K视频','galaxy','galaxy'),('kiosk视频','kiosk','kiosk')])
        approved_summary=(f'<h3>{"本轮用户授权生成范围" if runtime.get("user_authorized_scope") else "本轮已确认范围"} · {admitted["total"]:,}图</h3>'
                          f'<div class="overall-meters">{approved_cards}</div>'
                          f'<p class="section-desc">双档齐备{admitted["dual"]:,}/{admitted["total"]:,}图；完成数包含有效复用，生成完成后仍待人工验看。</p>')
    chapter_summary=''
    if runtime.get('chapters'):
        chapter_rows=''.join(
            f'<tr><th scope="row">第{esc(chapter["number"])}章 · {esc(chapter["title"])}</th>'
            +''.join('<td>'+bar(label,chapter[key],chapter['total'],tone)+'</td>'
                     for label,key,tone in [('音频','audio','audio'),('Galaxy 4K','galaxy','galaxy'),('kiosk','kiosk','kiosk')])
            +'</tr>' for chapter in runtime['chapters'])
        chapter_summary=('<h3>各章制作进度</h3><p class="section-desc">各章按主讲候选素材去重统计；同一棋图可供多章使用，章间数量不可相加。</p>'
                         '<div class="table-wrap"><table class="books"><thead><tr><th>章节</th><th>音频</th><th>Galaxy 4K</th><th>kiosk</th></tr></thead>'
                         '<tbody>'+chapter_rows+'</tbody></table></div>')
    overall=(f'<section id="media-progress" class="section"><div class="section-heading"><h2>音视频制作进度 · 两个统计范围</h2><span>更新：{stamp} · 北京时间</span></div>'
             +approved_summary+f'<h3>全部候选素材 · {n:,}图</h3>'
             f'<div class="overall-meters">{cards}</div><p class="section-desc">全批去重{n:,}条候选记录，含有效复用；双档齐备{c["dual"]:,}图。{esc(production_note)}'
             f'正式版已发布关联：{runtime["ogs_arranged_lessons"]}/{runtime["ogs_total_lessons"]}小节；素材制作、选编和发布分别记录。</p>'
             f'<p class="section-desc">每行分别统计主讲候选素材，补充素材可展开。不同小节可能引用同一图，各行数量不可直接相加。{esc(refresh_note)}</p>'
             +chapter_summary+'</section>')

production_update=data.get('production_update')
arrangement=data.get('arrangement_progress')
if arrangement:
    published = arrangement.get('production_manifest_url') is not None
    publication_note = (f'正式环境已发布{arrangement["production_lesson_count"]}节新版片单；原14节演示版保留用于回退。'
                        if published else f'正式环境仍为{arrangement["production_lesson_count"]}节原演示版；未发布新片单。')
    overall=(f'<aside class="note" id="arrangement-progress"><p><strong>OGS视频片单编排 · {esc(arrangement["status"])}</strong></p>'
             +bar('小节编排',arrangement['curated_lessons'],arrangement['total_lessons'],'galaxy')
             +f'<p>{arrangement["unique_selected_clips"]}段不同视频 · {arrangement["playlist_entries"]}次播放引用。'
             f'{esc(publication_note)}</p>'
             f'<p><a href="{esc(arrangement["review_document"])}">查看逐节片单、顺序、出处与覆盖说明 ↗</a> · '
             f'<a href="{esc(arrangement["preview_url"])}">打开本机TEST只读预览 ↗</a></p>'
             f'<p>{esc(arrangement["exercise_source"])}。{esc(arrangement["note"])}</p>'
             f'<p>{esc(arrangement["updated_at"])}</p></aside>'+overall)
if production_update:
    overall=(f'<aside class="note" id="production-update"><p><strong>{esc(production_update["title"])}</strong></p>'
             f'<p>{esc(production_update["message"])}</p><p>{esc(production_update["updated_at"])}</p></aside>'+overall)

page = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OGS视频讲解选材提纲 · 248小节来源对照</title><style>
:root{--paper:#f5f1e7;--surface:#fffdf7;--ink:#22332b;--muted:#63685f;--line:#d9dbcc;--green:#214f40;--green-light:#e8eee4;--clay:#8d5b36;--serif:"Songti SC","STSong",serif;--sans:"PingFang SC","Microsoft YaHei",sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:176px}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.75 var(--sans)}a{color:var(--green);text-underline-offset:4px}button,input,select{font:inherit}button,select{cursor:pointer}button,.action{min-height:44px;padding:9px 16px;border:1px solid var(--line);border-radius:5px;background:var(--surface);color:var(--ink);text-decoration:none}button:hover,.action:hover{background:var(--green-light)}:focus-visible{outline:3px solid var(--clay);outline-offset:3px}h1,h2,h3,p{margin:0}h1,h2{font-family:var(--serif)}h1{font-size:clamp(32px,3.8vw,52px);line-height:1.3;margin:15px 0 20px}h2{font-size:28px}h3{font-size:17px;line-height:1.6}.shell{max-width:1580px;margin:auto;padding:0 32px}.topbar{background:var(--paper);border-bottom:1px solid var(--line)}.topbar .shell{display:flex;justify-content:space-between;align-items:center;gap:20px;padding-top:16px;padding-bottom:16px}.brand{font:700 20px var(--serif);text-decoration:none}.brand:before{content:"● ○";margin-right:12px}.nav{display:flex;gap:22px;font-size:14px}.nav a{text-decoration:none}.hero{padding:48px 0 32px;max-width:1080px}.eyebrow{color:var(--clay);font-size:12px;letter-spacing:.1em}.desc{font-size:17px;color:var(--muted);max-width:970px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}.primary{background:var(--green);color:white;border-color:var(--green)}.primary:hover{background:#143c2d}.stats{display:grid;grid-template-columns:repeat(5,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:28px}.stat{padding:20px 24px;border-right:1px solid var(--line)}.stat:first-child{padding-left:0}.stat:last-child{border:0}.stat strong{font:38px/1.3 var(--serif);color:var(--green);margin-right:8px}.stat p{color:var(--muted);font-size:13px}.note{background:var(--green-light);padding:18px 22px;border-left:3px solid var(--green);margin-bottom:24px}.note strong{color:var(--green)}.note p+p{margin-top:7px}.section{padding:30px 0;border-top:1px solid var(--line)}.section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:24px;margin-bottom:14px}.section-desc{color:var(--muted);margin:8px 0 18px;max-width:1000px}.overview{max-width:1050px;width:100%;border-collapse:collapse;font-size:14px}.overview th,.overview td{text-align:left;padding:11px 15px;border-bottom:1px solid var(--line)}.overview thead{background:var(--green-light)}.overview th{font-weight:500}.gap-box{margin:22px 0 30px;padding:20px 24px;background:#fff6e7;border:1px solid #dbc4a0;border-radius:6px}.gap-box summary{cursor:pointer;font-weight:600;color:#785024}.gap-box ul{margin:14px 0 0;padding-left:22px}.gap-box li{padding:7px 0}.gap-box p{font-size:14px;color:var(--muted)}.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:13px;margin:14px 0 18px}.legend div{max-width:330px}.badge{display:inline-block;font-size:12px;border-radius:4px;padding:3px 9px;white-space:nowrap;font-weight:600}.direct{background:#e3eee3;color:#2b573e}.combined{background:#e8edec;color:#3c6062}.adapt{background:#f1e9d9;color:#80582c}.gap{background:#f5dfd5;color:#914723}.filters{position:sticky;top:0;z-index:5;background:var(--paper);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0 10px;box-shadow:0 3px 6px #22332b08}.filter-grid{display:grid;grid-template-columns:1fr 210px 150px auto;gap:12px;align-items:end}.filters label{display:flex;flex-direction:column;font-size:12px;color:var(--muted);gap:5px}.filters input,.filters select{height:44px;padding:8px 12px;background:var(--surface);border:1px solid var(--line);border-radius:5px;color:var(--ink);min-width:0}.filter-result{font-size:13px;color:var(--muted);margin-top:9px}.table-wrap{overflow-x:auto;border:1px solid var(--line);margin:18px 0 8px;background:var(--surface)}.mapping{width:100%;min-width:1050px;border-collapse:collapse;font-size:14px;table-layout:fixed}.mapping thead th{text-align:left;padding:13px 17px;background:var(--green-light);font-weight:500}.mapping thead th:nth-child(1){width:18%}.mapping thead th:nth-child(2){width:23%}.mapping thead th:nth-child(3){width:41%}.mapping thead th:nth-child(4){width:10%}.mapping thead th:nth-child(5){width:8%}.mapping td,.mapping tbody th{vertical-align:top;padding:20px 17px;border-bottom:1px solid var(--line);text-align:left;font-weight:400;overflow-wrap:anywhere}.mapping tbody tr.lesson-row:hover{background:#fafaf1}.mapping .chapter-row th{background:var(--green);color:white;padding:13px 17px;font-size:19px;font-family:var(--serif)}.chapter-row span{font:12px var(--sans);opacity:.75;margin-right:12px}.chapter-row small{font:12px var(--sans);opacity:.8;float:right;margin-top:7px}.course-code{display:block;color:var(--clay);font-size:13px;margin-bottom:4px;font-variant-numeric:tabular-nums}.subtext{font-size:13px;color:var(--muted);margin:7px 0}.ogs-link{display:inline-block;margin-top:9px;font-size:12px}.source-item+.source-item{margin-top:15px;padding-top:14px;border-top:1px dashed var(--line)}.book-title{font-weight:600;text-decoration:none}.book-title:hover{text-decoration:underline}.source-item>p{font-size:13px;margin-top:3px}.source-extra{font-size:11px;color:var(--muted);margin-top:5px}.source-extra a{text-decoration:none}.range-note{color:#8d5b36}.source-item .selection-note{font-size:12px;color:var(--muted);margin-top:4px}.supplement{margin-top:15px;font-size:12px;border-top:1px solid var(--line);padding-top:10px}.supplement summary{cursor:pointer;color:var(--green);font-weight:600}.supplement .source-item{margin-top:10px}.prep-note{font-size:11px;color:var(--muted);margin-top:9px}.steps strong{display:block;font-size:24px;font-weight:400;font-variant-numeric:tabular-nums;color:var(--green)}.steps span{font-size:11px;display:block;color:var(--muted)}.steps small{display:block;font-size:11px;margin-top:10px;color:var(--muted)}#empty{padding:45px;text-align:center;color:var(--muted)}[hidden]{display:none!important}.books{width:100%;border-collapse:collapse;font-size:14px}.books th,.books td{text-align:left;padding:11px 16px;border-bottom:1px solid var(--line);font-weight:400}.books thead{background:var(--green-light)}.books th:first-child{width:55%}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:var(--muted)}footer{padding:24px 0 45px;font-size:12px;color:var(--muted)}.back-top{position:fixed;bottom:20px;right:20px;box-shadow:0 3px 15px #22332b15}.skip{position:absolute;left:16px;top:-80px}.skip:focus{top:12px;background:white;padding:8px;z-index:10}
@media(max-width:900px){.shell{padding:0 20px}.nav{gap:12px;font-size:12px}.hero{padding:32px 0}.stats{grid-template-columns:repeat(3,1fr)}.stat{padding:14px!important;border-right:0}.stat strong{font-size:30px}.filter-grid{grid-template-columns:1fr 1fr}.filters label:first-child{grid-column:1/-1}.section-heading{align-items:start;flex-direction:column;gap:8px}.mapping{min-width:1100px}.legend{gap:10px}.topbar .shell{flex-wrap:wrap}.books th:first-child{width:auto}}
@media print{body{background:white;font-size:10px}.shell{max-width:none;padding:0}.topbar,.hero-actions,.filters,.back-top,.source-extra,.ogs-link,.gap-box{display:none}.hero{padding:0 0 16px}h1{font-size:28px}.stats{margin-bottom:14px}.stat{padding:10px}.stat strong{font-size:24px}.table-wrap{overflow:visible;border:none}.mapping{min-width:0;font-size:10px}.mapping td,.mapping tbody th,.mapping thead th{padding:8px}.mapping thead{display:table-header-group}.chapter-row th{break-after:avoid}.source-item>p{font-size:10px}.source-item .selection-note{font-size:9px}.prep-note,.steps small{font-size:8px}.badge{font-size:9px}.supplement{font-size:9px}a{text-decoration:none;color:inherit}.books{font-size:10px}.legend{font-size:10px}.section{padding:16px 0}.stat p{font-size:10px}}@page{size:A3 landscape;margin:12mm}

/* Existing paper/green design; text counts remain readable without colour. */
.overall-meters{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin:18px 0}.overall-card{padding:20px 22px;background:var(--surface);border:1px solid var(--line);border-radius:6px}.meter{margin:12px 0;--meter-color:var(--green)}.meter>div{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:12px;margin-bottom:6px}.meter strong{font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}.meter.audio{--meter-color:#536d84}.meter.kiosk{--meter-color:var(--clay)}.meter progress{display:block;width:100%;height:7px;border:0;border-radius:9px;background:var(--green-light);overflow:hidden;appearance:none;-webkit-appearance:none}.meter progress::-webkit-progress-bar{background:var(--green-light);border-radius:9px}.meter progress::-webkit-progress-value{background:var(--meter-color);border-radius:9px}.meter progress::-moz-progress-bar{background:var(--meter-color);border-radius:9px}.overall-card .meter>div{font-size:15px;flex-wrap:wrap}.overall-card .meter strong{font-size:24px}.overall-card .meter progress{height:11px}.production-stage{font-size:13px;color:var(--green);font-weight:600}.progress-basis{font-size:12px;color:var(--muted);margin:4px 0 12px}.pending-note{font-size:12px;color:var(--clay);margin:9px 0}.ogs-stage{font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:10px;margin-top:12px}.production-progress .supplement{font-size:12px}.mapping{min-width:1350px}.mapping thead th:nth-child(1){width:15%}.mapping thead th:nth-child(2){width:18%}.mapping thead th:nth-child(3){width:30%}.mapping thead th:nth-child(4){width:10%}.mapping thead th:nth-child(5){width:7%}.mapping thead th:nth-child(6){width:20%}
@media(max-width:900px){.overall-meters{grid-template-columns:1fr}.mapping{min-width:1350px}}@media print{.mapping{min-width:0}.meter>div,.production-stage,.progress-basis,.pending-note,.ogs-stage{font-size:9px}.overall-card .meter strong{font-size:18px}}
</style></head><body>
<a class="skip" href="#outline">跳至完整对照表</a>
<header class="topbar"><div class="shell"><a class="brand" href="go-curriculum.html">围棋课程地图</a><nav class="nav" aria-label="页面目录"><a href="#media-progress">制作进度</a><a href="#overview">章节总览</a><a href="#outline">248小节对照</a><a href="#books">23本书目</a><a href="#provenance">核验说明</a></nav></div></header>
<main class="shell" id="top"><section class="hero"><p class="eyebrow">视频教程 · 选材提纲与制作进度 · 2026.11.12</p><h1>先讲清楚，再动手下棋。<br>OGS每一小节，都有书本可循。</h1><p class="desc">沿用kiosk现有OGS的章节与小节，从23本核心教材中选择视频讲解素材，连接「先看视频 → 再做OGS练习」的学习顺序。Galaxy后续也沿用这条课程主线。</p><div class="hero-actions"><a class="action primary" href="#outline">查看完整来源对照 ↓</a><a class="action" href="@@BASE@@.csv" download>下载CSV表格</a><button type="button" id="print">打印 / 保存PDF</button></div></section>
<div class="stats" aria-label="提纲统计"><div class="stat"><strong>7</strong>章<p>以测试后台课程为准</p></div><div class="stat"><strong>248</strong>小节<p>保留每个原始小节</p></div><div class="stat"><strong>3,551</strong>步骤<p>OGS原练习步骤，非视频数</p></div><div class="stat"><strong>12 / 23</strong>本<p>本轮选材 / 核心教材</p></div><div class="stat"><strong>3</strong>处<p>需要补充专门素材</p></div></div>
@@MEDIA_PROGRESS@@
<div class="note"><p><strong>页码统一：所有页码都是从1开始的PDF物理页码，不是书上印刷页码。</strong>点击书名可打开本机PDF；点击“测试后台棋图”可跳转该页段内已存在的一幅电子棋图，需本机测试后台可访问。</p><p>这是<strong>章节与候选页段的选材提纲</strong>。对应章节不代表已经逐幅选定题图、逐题配好视频或完成内容审核。同一基础讲解可以复用，但248小节分别保留自己的学习目标和练习入口。</p><p>部分素材超过此前首本PDF前50页的制作范围，已逐段标出。候选素材正在制作；已有视频仍需按OGS目标选取编排。</p></div>
<section id="overview" class="section"><div class="section-heading"><h2>七个章节，一条主线</h2><span>视频讲解在前，原OGS练习在后</span></div><table class="overview"><thead><tr><th scope="col">OGS章节</th><th scope="col">小节数</th><th scope="col">练习步骤</th><th scope="col">选材对应程度</th></tr></thead><tbody>@@SUMMARY@@</tbody></table>
<details class="gap-box" open><summary>3处需要补充专门素材</summary><ul>@@GAPS@@</ul></details></section>
<section id="outline" class="section"><h2>完整小节 × 教材来源对照</h2><p class="section-desc">每行对应一个OGS小节。主讲取材直接展示，补充取材可展开；可按章节、对应程度筛选，也可搜索书名、主题、章节或页码。书籍章节可能由多个OGS小节复用，并不要求把整段逐页拍成视频。</p>
<div class="legend"><div><span class="badge direct">直接对应 · 72</span> 已定位同主题教材章节。</div><div><span class="badge combined">跨章组合 · 67</span> 需要合并不同概念或正反例。</div><div><span class="badge adapt">需改编 · 106</span> 候选段需降难度、截局部或逐题选例。</div><div><span class="badge gap">需补充 · 3</span> 基础原理有来源，专门例图或操作说明待补。</div></div>
<div class="filters"><div class="filter-grid"><label>搜索书名 / 主题 / 小节编号<input type="search" id="search" placeholder="例如：打吃、入门篇、6.35、假眼"></label><label>OGS章节<select id="chapter"><option value="">全部7章</option>@@CHAPTER_OPTIONS@@</select></label><label>对应程度<select id="status"><option value="">全部程度</option>@@STATUS_OPTIONS@@</select></label><button type="button" id="reset">重置筛选</button></div><p id="result" class="filter-result" role="status" aria-live="polite">显示248 / 248小节 · 3,551练习步骤</p></div>
<div class="table-wrap"><table class="mapping"><caption class="skip">OGS全部章节与小节对应的教材章节和PDF页码</caption><thead><tr><th scope="col">OGS章节 / 小节</th><th scope="col">视频应讲清楚什么</th><th scope="col">主讲与补充取材 · 原章节 / PDF页码</th><th scope="col">对应程度</th><th scope="col">后续练习</th><th scope="col">制作进度 · 主讲候选素材</th></tr></thead><tbody>@@ROWS@@</tbody></table><p id="empty" hidden>没有符合条件的小节。请清空关键词或重置筛选。</p></div><p class="section-desc">练习步骤数来自现有OGS目录；一个步骤可能是说明、选点或实际落子，并不等同于一道独立习题。</p></section>
<section id="books" class="section"><h2>23本核心书籍的使用范围</h2><p class="section-desc">本轮优先取12本中适合入门与初级的章节；其余11本留给后续中高级与实战扩展。来源引用次数可重复，不是独立题图数量，也不是计划视频数。</p><table class="books"><thead><tr><th scope="col">核心书籍 / 本机PDF</th><th scope="col">PDF总页数</th><th scope="col">本轮角色</th></tr></thead><tbody>@@BOOKS@@</tbody></table></section>
<section id="provenance" class="section"><h2>核验口径与下一步</h2><p class="section-desc">OGS范围取自测试后台书籍ID80的课程目录：7章、248小节、3,551步骤。教材范围由23本核心书籍的现有结构化章节、原始PDF及测试库电子棋图交叉定位；PDF页数已核对。页段是取材建议，具体例题还需在准备素材时核对原图、正解、难度及识别疑点。</p><ol><li>审核这份章节 / 小节 / 来源页码提纲，先确认覆盖与顺序。</li><li>按小节挑出完整例图与正反变化，结合原PDF准备连贯解说；书中未画明的气点、箭头、路线等可据教学目标补画。</li><li>先生成音频，再按语音时间线生成Galaxy 4K与kiosk 7英寸两版视频；字幕、标记及落子随语音出现。</li><li>先在测试后台查看效果，确认后再把选中的视频关联到OGS小节；素材生成进度见上表，OGS小节尚待选编和关联。</li></ol><details><summary>课程来源版本与可复用数据</summary><pre>@@PROVENANCE@@</pre><p>课程内容SHA-256：@@SHA@@</p><p><a href="@@BASE@@.json" download>下载结构化提纲JSON</a> · <a href="@@BASE@@.csv" download>下载完整CSV</a></p></details></section>
</main><footer class="shell">2026.11.12 · 选材提纲待审 · 返回<a href="go-curriculum.html#progress">教材制作进度</a></footer><a class="action back-top" href="#top">回到顶部 ↑</a>
<script>
const q=document.getElementById('search'),chapter=document.getElementById('chapter'),status=document.getElementById('status');
const rows=Array.from(document.querySelectorAll('.lesson-row'));
function filter(){const needle=q.value.trim().toLowerCase(),seen=new Set();let count=0,steps=0;for(const row of rows){const yes=(!needle||row.dataset.search.includes(needle))&&(!chapter.value||row.dataset.chapter===chapter.value)&&(!status.value||row.dataset.status===status.value);row.hidden=!yes;if(yes){seen.add(row.dataset.chapter);count++;steps+=Number(row.querySelector('.steps strong').textContent)}}for(const heading of document.querySelectorAll('.chapter-row'))heading.hidden=!seen.has(heading.dataset.heading);document.getElementById('empty').hidden=count>0;document.getElementById('result').textContent=`显示${count} / 248小节 · ${steps.toLocaleString('zh-CN')}练习步骤`;}
function clear(){q.value='';chapter.value='';status.value='';filter()}
q.addEventListener('input',filter);chapter.addEventListener('change',filter);status.addEventListener('change',filter);document.getElementById('reset').addEventListener('click',clear);
document.getElementById('print').addEventListener('click',()=>window.print());
document.querySelectorAll('[data-chapter-link]').forEach(a=>a.addEventListener('click',()=>{clear();chapter.value=a.dataset.chapterLink;filter()}));
document.querySelectorAll('[data-lesson-link]').forEach(a=>a.addEventListener('click',()=>clear()));
if(location.hash.startsWith('#lesson-'))clear();
</script></body></html>
'''
for key, value in {
    'BASE': BASE, 'SUMMARY': ''.join(summary_rows), 'GAPS': ''.join(gaps),
    'CHAPTER_OPTIONS': chapter_options, 'STATUS_OPTIONS': status_options,
    'ROWS': ''.join(table_rows), 'BOOKS': ''.join(book_rows),
    'PROVENANCE': provenance, 'SHA': esc(data['source_content_sha256']), 'MEDIA_PROGRESS': overall,
}.items():
    page = page.replace('@@' + key + '@@', value)
assert '@@' not in page
target=DOCS / (BASE + '.html')
tmp=target.with_suffix('.html.tmp')
tmp.write_text(page)
tmp.replace(target)
print(DOCS / (BASE + '.html'))
