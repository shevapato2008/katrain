"""Render a standalone, searchable report from read-only database exports."""

import argparse
import json
from datetime import datetime
from pathlib import Path


HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>棋谱库 · 五语言翻译进度</title><link rel="icon" href="data:,">
<style>
:root{--ink:#202923;--muted:#59665d;--paper:#f6f7f2;--line:#dce2d8;--accent:#2f694c}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,"PingFang SC","Noto Sans CJK SC",sans-serif}
main{max-width:1500px;margin:auto;padding:40px 32px}header{display:flex;gap:28px;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:26px}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.16em;color:var(--accent)}h1{font-size:clamp(28px,4vw,42px);line-height:1.25;letter-spacing:-.03em;margin:12px 0}h2{font-size:22px;margin:0}p{margin:8px 0;color:var(--muted)}
.stones{display:flex;align-items:center;gap:12px}.stone{width:54px;height:54px;border-radius:50%;background:var(--ink);box-shadow:inset 0 0 0 5px var(--ink),inset 0 0 0 7px white}.stone.white{background:white;border:1px solid #b5bdb6;box-shadow:inset 0 0 0 5px white,inset 0 0 0 7px var(--ink)}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:26px 0}.metric{padding:20px;border:1px solid var(--line);background:white;border-radius:14px}.metric .value{display:block;font-size:32px;line-height:1.3;font-weight:700;font-variant-numeric:tabular-nums}.metric .label{font-size:14px;color:var(--muted)}.metric small{display:block;margin-top:6px;color:var(--accent)}
progress{display:block;width:100%;height:6px;appearance:none;border:0;border-radius:3px;margin-top:15px;background:#e8eee6}progress::-webkit-progress-bar{background:#e8eee6;border-radius:3px}progress::-webkit-progress-value{background:var(--accent);border-radius:3px}progress::-moz-progress-bar{background:var(--accent)}
.note{background:#eaf0e7;border-left:3px solid var(--accent);padding:16px 20px;border-radius:4px;margin:24px 0;color:#3e5043;font-size:14px}.note strong{color:var(--ink)}
.panel{background:white;border:1px solid var(--line);border-radius:16px;overflow:hidden}.panel-header{padding:24px}.toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin-top:18px}.toolbar label{display:flex;flex-direction:column;gap:6px;font-size:12px;color:var(--muted)}.toolbar .search{flex:1;min-width:210px}input,select,button{min-height:44px;border:1px solid #cbd4c8;border-radius:8px;background:white;color:var(--ink);padding:9px 12px;font:inherit}button,select{cursor:pointer}button:hover{background:#edf3e9}button:disabled{opacity:.5;cursor:default}input:focus-visible,select:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #65a77d;outline-offset:2px}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;font-size:12px;color:var(--muted);background:#f1f4ee;padding:12px 16px;white-space:nowrap}td{padding:14px 16px;border-top:1px solid #e8ece5;vertical-align:top}td:first-child{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px}td:nth-child(2){min-width:135px;font-weight:600}td.name{min-width:130px}td:last-child{white-space:nowrap}.empty{color:#81897f;font-size:12px}a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.badge{display:inline-block;background:#e7f2e9;border:1px solid #c8dfcd;color:#275b3d;padding:3px 9px;border-radius:20px;font-size:12px;font-weight:500}.badge.pending{background:#f4f4ee;border-color:#dfe2d6;color:#68735f}.method{display:block;font-size:11px;color:var(--muted);font-weight:400;margin-top:3px}
.footer{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px 24px;border-top:1px solid var(--line);font-size:14px;color:var(--muted)}.footer .buttons{display:flex;gap:8px}.meta{font-size:12px;color:var(--muted);margin-top:20px}.muted{color:var(--muted);font-size:12px}details{margin-top:8px;font-size:12px;font-weight:400}summary{cursor:pointer;color:var(--accent)}details a{display:block;margin-top:5px;max-width:240px;overflow-wrap:anywhere}
@media(max-width:800px){main{padding:24px 16px}.metrics{grid-template-columns:repeat(2,1fr)}.metric{padding:16px}.metric .value{font-size:27px}.stones{display:none}.panel-header{padding:18px}.footer{padding:16px;flex-wrap:wrap}th,td{padding:12px}}
</style>
<main><header><div><div class="eyebrow">STELLABOX / KIFU LIBRARY</div><h1>棋谱库 · 五语言翻译进度</h1><p id="subtitle"></p></div><div class="stones" aria-hidden="true"><span class="stone"></span><span class="stone white"></span></div></header>
<section class="metrics" aria-label="已写入正式数据库的统计" id="metrics"></section>
<div class="note" id="note"></div>
<section class="panel"><div class="panel-header"><h2>棋手与赛事目录</h2><p class="muted">按关联棋局数量排序；点击译名打开依据页面。空白明确标为待翻译。</p>
<div class="toolbar"><label>目录<select id="kind"><option value="player">棋手</option><option value="event">赛事类型</option></select></label><label>完成状态<select id="state"><option value="all">全部</option><option value="done">五语齐全</option><option value="pending">尚未齐全</option></select></label><label class="search">按默认名、ID或任何已有译名搜索<input id="search" type="search" placeholder="例如：吴清源、Go Seigen、LG Cup"></label><label>每页<select id="size"><option>50</option><option>100</option></select></label></div></div>
<div class="table-wrap"><table><thead><tr><th>ID</th><th>默认名称 / 覆盖棋局</th><th>简体中文</th><th>繁體中文</th><th>日本語</th><th>한국어</th><th>English</th><th>状态</th></tr></thead><tbody id="rows"></tbody></table></div>
<div class="footer"><span id="pagination" aria-live="polite"></span><div class="buttons"><button id="prev">上一页</button><button id="next">下一页</button></div></div></section>
<div class="meta" id="metadata"></div></main>
<script id="data" type="application/json">__DATA__</script>
<script>
const {statistics:s,catalog:c,generated_at}=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id), num=n=>Number(n).toLocaleString('zh-CN'), pct=n=>Number(n).toFixed(2)+'%';
const byKind={},done={};let page=1;
for(const kind of ['player','event']){const names=new Map();for(const n of c.names[kind]){if(!names.has(n.owner_id))names.set(n.owner_id,{});names.get(n.owner_id)[n.lang]=n}
done[kind]=new Set(s[kind+'s_done'].map(r=>r[kind+'_id']));byKind[kind]=c[kind+'s'].map(r=>({...r,names:names.get(r.id)||{},done:done[kind].has(r.id)}))}
$('subtitle').textContent='正式数据库快照 · '+generated_at+' · 共 '+num(s.games)+' 盘棋局';
for(const [label,value,total,percent] of [['棋手五语齐全',s.players_done_count,s.player_total,s.players_done_count_pct],['赛事五语齐全',s.events_done_count,s.event_total,s.events_done_count_pct],['赛事译名覆盖棋局',s.event_five_lang_games,s.games,s.event_five_lang_games_pct],['双方棋手与赛事均齐全',s.complete_five_lang_games,s.games,s.complete_five_lang_games_pct]]){
const card=document.createElement('div');card.className='metric';const lab=document.createElement('div');lab.className='label';lab.textContent=label;const val=document.createElement('span');val.className='value';val.textContent=num(value);const small=document.createElement('small');small.textContent='共 '+num(total)+' · '+pct(percent);const bar=document.createElement('progress');bar.max=100;bar.value=percent;bar.setAttribute('aria-label',label+' '+pct(percent));card.append(lab,val,small,bar);$('metrics').append(card)}
$('note').textContent='统计口径：五语为简体、繁体、日文、韩文、英文，仅计入已经独立批准并写入数据库的名称；赛事采用原文直译的单元格明确标注。双方棋手五语齐全覆盖 '+num(s.both_players_five_lang_games)+' 盘（'+pct(s.both_players_five_lang_games_pct)+'）。未完成的原文和中文首遍展示不计为五语齐全。';
$('metadata').textContent='本页是离线统计快照，不会自动刷新。已关联棋手槽位 '+num(s.linked_player_slots)+' / '+num(s.games*2)+'，已关联赛事 '+num(s.linked_event_games)+' / '+num(s.games)+'。隐藏疑难记录 '+num(s.hidden_games)+' 盘，公开列表 '+num(s.listed_games)+' 盘（另排除 9 盘重复记录）。赛事表列出比赛类型，同届不同轮次不创建新类型 ID。';
function render(){const kind=$('kind').value,q=$('search').value.trim().toLocaleLowerCase(),state=$('state').value,size=Number($('size').value);const list=byKind[kind].filter(r=>(state==='all'||(state==='done')===r.done)&&(!q||[r.id,r.canonical_name,...Object.values(r.names).map(n=>n.display_name)].join(' ').toLocaleLowerCase().includes(q)));const pages=Math.max(1,Math.ceil(list.length/size));page=Math.min(page,pages);$('rows').replaceChildren();
for(const r of list.slice((page-1)*size,page*size)){const tr=document.createElement('tr');for(const value of [r.id,r.canonical_name]){const td=document.createElement('td');td.textContent=value;tr.append(td)}const counts=document.createElement('div');counts.className='muted';counts.textContent=num(r.games)+' 盘'+(kind==='player'?' · '+num(r.slots)+' 个棋手槽位':'');tr.children[1].append(counts);
const sources=(r.authoritative_pages||[]).filter(p=>typeof p.url==='string'&&p.url.startsWith('https://'));if(sources.length){const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=sources.length+' 个资料页面';details.append(summary);for(const p of sources){const link=document.createElement('a');link.href=p.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=[p.source_id,p.language].filter(Boolean).join(' · ');link.title=p.url;details.append(link)}tr.children[1].append(details)}
for(const lang of ['cn','tw','jp','ko','en']){const td=document.createElement('td');td.className='name';const n=r.names[lang];if(n){const language={cn:'zh-Hans',tw:'zh-Hant',jp:'ja',ko:'ko',en:'en'}[lang];const source=sources.find(p=>p.language===language&&p.role==='wikipedia_article')||sources.find(p=>p.language===language)||sources.find(p=>p.role==='official');const url=source?.url||n.reference_url;const el=document.createElement(url&&/^https:\/\//.test(url)?'a':'span');el.textContent=n.display_name;if(el.tagName==='A'){el.href=url;el.target='_blank';el.rel='noopener noreferrer';el.title='查看名称依据'}td.append(el);if(n.decision_kind==='translated'){const mark=document.createElement('span');mark.className='method';mark.textContent='原文直译';td.append(mark)}}else{td.textContent='待翻译';td.classList.add('empty')}tr.append(td)}const status=document.createElement('td'),badge=document.createElement('span');badge.className='badge'+(r.done?'':' pending');badge.textContent=r.done?'五语齐全':Object.keys(r.names).length+' / 5';status.append(badge);tr.append(status);$('rows').append(tr)}
if(!list.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=8;td.textContent='没有符合条件的名称';tr.append(td);$('rows').append(tr)}$('pagination').textContent='匹配 '+num(list.length)+' 项 · 第 '+page+' / '+pages+' 页';$('prev').disabled=page===1;$('next').disabled=page===pages}
for(const id of ['kind','state','size'])$(id).addEventListener('change',()=>{page=1;render()});$('search').addEventListener('input',()=>{page=1;render()});$('prev').addEventListener('click',()=>{page--;render()});$('next').addEventListener('click',()=>{page++;render()});render();
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--statistics', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = {
        'statistics': json.loads(args.statistics.read_text()),
        'catalog': json.loads(args.catalog.read_text()),
        'generated_at': datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z'),
    }
    # Prevent embedded raw metadata from terminating the JSON script element.
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\u003c')
    args.output.write_text(HTML.replace('__DATA__', payload), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
