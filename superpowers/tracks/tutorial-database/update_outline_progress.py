#!/usr/bin/env python3
"""Report current media coverage per OGS source row; never creates or reviews media."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
BASE='ogs-video-outline-2026-11-12'
BATCH=REPO/'data/tutorial_media_batches/ogs-book-sources-20261113'


def current_sets(live):
    result={key:set() for key in ('audio','galaxy','kiosk')}
    for task in live['tasks']:
        figure=live['current'][str(task['figure_id'])]
        if not figure.get('generation_authorized',figure['approved']) or not figure['pronunciation_current'] or task['status']!='succeeded':
            continue
        if task['audio_sha256']!=figure['audio_sha256'] or task['narration_sha256']!=figure['narration_sha256']:
            continue
        if task['kind']=='audio':
            result['audio'].add(task['figure_id'])
        elif task['animated'] and task['video_asset']==figure['profiles'].get(task['profile']):
            key={'galaxy-4k-v1':'galaxy','kiosk-7-v1':'kiosk'}.get(task['profile'])
            if key:result[key].add(task['figure_id'])
    result['dual']=result['audio']&result['galaxy']&result['kiosk']
    return result


def update():
    manifest=json.loads((HERE/(BASE+'.json')).read_text())
    snapshot=json.loads((BATCH/'snapshot.json').read_text())
    live=json.loads((BATCH/'tasks-latest.json').read_text())
    summary=json.loads((BATCH/'progress.json').read_text())
    published_path=HERE/'demo-7inch-2026-11-15/production-manifest.json'
    published=json.loads(published_path.read_text()) if published_path.exists() else {}
    published_playlists=published.get('playlists',{}) if published.get('prototype_only') is False else {}
    sets=current_sets(live)
    figures={row['figure']['id']:(book['book_id'],row['figure']['page']) for book in snapshot['books'] for row in book['figures']}
    unit_ids={key:{fid for fid,(bid,page) in figures.items() if bid==unit['book_id'] and unit['pdf_pages'][0]<=page<=unit['pdf_pages'][1]} for key,unit in manifest['source_units'].items()}

    def coverage(ids):
        return {'total':len(ids),**{key:len(ids&value) for key,value in sets.items()},
                'pending_static_confirmation':sum(not live['current'][str(fid)]['approved'] for fid in ids),
                'pending_generation_authorization':sum(not live['current'][str(fid)].get('generation_authorized',live['current'][str(fid)]['approved']) for fid in ids)}

    def combine(keys):
        return set().union(*(unit_ids[key] for key in keys)) if keys else set()

    for lesson in manifest['lessons']:
        primary=combine(lesson['primary_sources'])
        supplemental=combine(lesson['supplementary_sources'])-primary
        counts=coverage(primary)
        if not counts['total']:stage='待选演示素材'
        elif counts['dual']==counts['total']:stage='主讲候选素材齐备'
        elif any(counts[key] for key in ('audio','galaxy','kiosk')):stage='已暂停 · 部分候选素材齐备' if summary.get('status')=='paused' else '候选素材制作中'
        elif counts['pending_generation_authorization']==counts['total']:stage='待生成授权'
        else:stage='已暂停 · 未制作' if summary.get('status')=='paused' else '待生成'
        if summary.get('status')=='runnable_scope_generated_with_source_exclusions' and counts['dual']<counts['total']:
            stage='清晰素材已完成 · 排除项保留'
        lesson['media_progress']={'updated_at':summary['updated_at'],'primary':counts,'supplementary':coverage(supplemental),
                                  'stage':stage,'ogs_stage':f"演示版已关联（{len(published_playlists[lesson['id']])}段）" if lesson['id'] in published_playlists else '待选编 / 待关联'}
    manifest['media_progress']={'updated_at':summary['updated_at'],'status':summary.get('status'),'overall':coverage(set(figures)),
                                'basis':'全批按去重后的1946幅选材棋图计算，含有效复用；每行按其主讲候选页段的去重图数计算，补充素材另列。生成采用用户明确授权或原有效人工确认；待静态人工确认标记与疑点保留，未完成图仍包含在分母中；素材生成不表示人工审核通过或OGS小节已选编关联。',
                                'ogs_arranged_lessons':sum(lesson['id'] in published_playlists for lesson in manifest['lessons']),'ogs_total_lessons':len(manifest['lessons'])}
    resume_path=BATCH/'resume-full-20261117/resume-request.json'
    resume=json.loads(resume_path.read_text()) if resume_path.exists() else {}
    if summary.get('status')=='runnable_scope_generated_with_source_exclusions':
        manifest['production_update']={'title':'本轮可制作素材已全部完成',
            'message':f"累计已生成{summary['completed_figures']}/{summary['figures']}幅真实音频及双档视频（含有效复用），本轮补齐{summary['execution_new_completed_figures']}幅，当前{len(summary['active_tasks'])}项在途。保留{resume['unresolved_source_or_calibration']}项来源或校准问题、{resume['non_diagram_placeholders']}项非实体占位。OGS小节的选编关联进度另列。",
            'updated_at':summary['updated_at']}
    elif summary.get('status')=='paused' and resume.get('status')=='preparing':
        manifest['production_update']={'title':'已收到继续指令，正在恢复制作',
            'message':f"当前已完成{summary['completed_figures']}/{summary['figures']}幅音频及双档视频，正在核对新执行批次。预计续做{resume['clear_remaining_expected']}幅清晰缺项；{resume['unresolved_source_or_calibration']}项来源或校准问题及{resume['non_diagram_placeholders']}项非实体占位保留。旧控制器维持停用，不重复制作成品，不启动机器审核。",
            'updated_at':summary['updated_at']}
    elif summary.get('status')=='paused':
        manifest['production_update']={'title':'音视频批量制作已暂停',
            'message':f"按用户要求，已完成当时开工的16幅当前图后停止。现有{summary['completed_figures']}幅真实音频及双档视频，在途0；不自动续图、补洞或恢复旧控制器。",
            'updated_at':summary['updated_at']}
    else:
        manifest['production_update']={'title':'音视频批量制作已恢复',
            'message':f"已生成{summary['completed_figures']}/{summary['figures']}幅真实音频及双档视频，当前{len(summary['active_tasks'])}项在途任务。仅续做未完成清晰素材，保留来源疑点；先语音再生成Galaxy 4K及7英寸双档，不自动派发机器审核。演示版已关联的小节另列，不把整份候选素材齐备算作全量课程已发布。",
            'updated_at':summary['updated_at']}
    manifest['media_progress']['chapters']=[
        {'number':chapter['number'],'title':chapter['title'],
         **coverage(combine([key for lesson in manifest['lessons']
                             if str(lesson['course_code']).split('.')[0]==str(chapter['number'])
                             for key in lesson['primary_sources']]))}
        for chapter in manifest['chapters']]
    admitted=BATCH/'resume-20261114/resume-manifest.json'
    if admitted.exists():
        eligible={fid for book in json.loads(admitted.read_text())['books'] for fid in book['eligible_ids']}
        manifest['media_progress']['approved_scope']=coverage(eligible&set(figures))
    full_grants=BATCH/'resume-full-20261114/generation-grants.json'
    if full_grants.exists():
        eligible=set(json.loads(full_grants.read_text())['authorized_ids'])
        manifest['media_progress']['user_authorized_scope']=coverage(eligible&set(figures))
    target=HERE/(BASE+'.json');tmp=target.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');tmp.replace(target)

    target=HERE/(BASE+'.csv')
    with target.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);fields=list(reader.fieldnames);rows=list(reader)
    extra=['主讲候选图总数','音频完成图','音频完成百分比','Galaxy4K完成图','Galaxy4K完成百分比','kiosk完成图','kiosk完成百分比','双档齐备图','待静态确认图','制作阶段','OGS编排关联阶段','进度更新时间']
    fields=[field for field in fields if field not in extra]+extra
    by_code={lesson['course_code']:lesson['media_progress'] for lesson in manifest['lessons']}
    def percent(done,total):return f'{100*done/total:.1f}%' if total else '未定数量'
    for row in rows:
        progress=by_code[row['小节编号']];c=progress['primary'];n=c['total']
        row.update(dict(zip(extra,[n,c['audio'],percent(c['audio'],n),c['galaxy'],percent(c['galaxy'],n),c['kiosk'],percent(c['kiosk'],n),c['dual'],c['pending_static_confirmation'],progress['stage'],progress['ogs_stage'],progress['updated_at']])))
    tmp=target.with_suffix('.csv.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    tmp.replace(target)
    return manifest['media_progress']


if __name__=='__main__':
    print(json.dumps(update(),ensure_ascii=False))
