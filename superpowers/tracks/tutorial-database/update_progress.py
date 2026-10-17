#!/usr/bin/env python3
"""Refresh the copied curriculum's production stages; never writes tutorial data."""
import argparse
import fcntl
import hashlib
from datetime import datetime
from html import escape
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = Path('/Users/fan/Repositories/go-topic-collections/curriculum/recognition-comparison/curriculum-gpt61sol-v1')
START, END = '<!-- TUTORIAL_PROGRESS_START -->', '<!-- TUTORIAL_PROGRESS_END -->'


def refresh(data, output):
    for book in data['books']:
        folder = output / book['catalog_id']
        result = folder / 'results.json'
        if not result.exists():
            continue
        value = json.loads(result.read_text())
        if value.get('catalog_id') != book['catalog_id']:
            raise ValueError(f"source identity mismatch: {book['catalog_id']}")
        summary = value['summary']
        complete, total = summary['pages_recognized_validated'], value['pdf_pages']
        figures, failed = summary['completed'], summary['failed_pages']
        correction = folder / 'p010-detection-override.json'
        unresolved = correction.exists() and json.loads(correction.read_text()).get('status') != 'applied_and_validated'
        if unresolved:
            book['recognition'] = f'识别中 · 第10页分图修正待完成（原始结果已归档）'
        else:
            stage = '已识别' if complete == total and failed == 0 else '识别中'
            book['recognition'] = f'{stage} · {complete}/{total}页 · {figures}图'
        if not book.get('validation_import_manually_set'):
            book['validation_import'] = (f"机器校验 {complete}/{total}页；失败{failed}；"
            f"疑点{summary['uncertain_figures']}图；待整书TEST入库")
        book['updated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')


def table(data):
    rows = []
    for number, book in enumerate(data['books'], 1):
        title = f'<a class="book-ref" href="#book-{escape(book["catalog_id"],quote=True)}">{escape(book["title"])}</a>'
        title += '<small>' + escape('；'.join(book['roles'])) + '</small>'
        fields = [str(number),title]+[escape(book[key]) for key in ('recognition','validation_import','human_review','voice','video')]
        fields.append(escape((book.get('updated_at') or '待开始')[:19]))
        rows.append(f'<tr data-book-id="{escape(book["catalog_id"],quote=True)}">'+''.join(f'<td>{text}</td>' for text in fields)+'</tr>')
    headers = ['顺序','教材与模块角色','棋图识别','机器验证 / TEST入库','人工校准审核','语音生成','2D视频生成','最近更新']
    return ('<section class="section" id="progress"><div class="section-heading"><div><div class="section-title">'
        '<span class="section-kicker">PRODUCTION PROGRESS</span><h2>教程制作进度</h2></div>'
        '<p class="section-intro">78本独立书源；先覆盖各模块核心教材，同层按模块轮转、多卷分轮推进；跨模块重复书只处理一次。'
        '识别、机器校验、人工审核与音视频分别记录；“已识别”不代表人工审核通过。原书单的正文解析完成仅指文字与结构，不代表电子棋图已完成。</p>'
        '<p><strong>当前连续执行目标：23本核心教材，5,827个PDF页。</strong>其他层级后置；已运行的《围棋入门速成》继续，但不计入23本。</p>'
        '<p>每本每完成10个PDF页在session汇报；每本完成识别后更新本表。语音及视频不会随本轮识别自动批量生成。'
        '<a href="plan.md">当前执行说明</a> · <a href="progress.json">进度数据</a></p></div></div>'
        '<div class="table-wrap progress-table-wrap"><table aria-label="78本教材制作阶段">'
        '<thead><tr>'+''.join(f'<th scope="col">{text}</th>' for text in headers)+'</tr></thead><tbody>'
        +''.join(rows)+'</tbody></table></div></section>')


def render_plan(data):
    active = [book for book in data['books'] if book['updated_at']]
    rows = '\n'.join('| '+book['title']+' | '+book['recognition']+' | '+book['validation_import']+' |' for book in active)
    return f'''# 教程数据库：当前执行说明与进度

更新：{datetime.now().astimezone().isoformat(timespec='seconds')}

本文件已替换早期媒体存储迁移计划，以本轮实际任务为准。完整书单、教学模块与78本制作阶段见 [go-curriculum.html](go-curriculum.html#progress)；状态数据保存在 [progress.json](progress.json)。

## 当前范围

- 当前连续执行目标为23本核心教材、5827个PDF页，直到识别、校验和TEST增量接入完成；完成一本即接下一核心书。其他层级后置；已运行的intro-fast继续，但不计入23本。人工审核及媒体独立记录，不自动完成。
- 78本真实书源按核心教材 → 练习/专项/纠错 → 提高/棋风比较 → 模块内补充 → 独立补充专题推进；每层按模块轮转、每轮每模块一本，多卷分轮，跨模块重复书只识别一次。
- 当前已启动的入门上卷、下卷和速成书继续；接下来三个新增任务是《围棋的筋和形》《李昌镐精讲围棋死活·第1卷》《布局基础》。模块13首选《简明形势判断》，石田书复用完成结果，不替代主教材。
- 使用 `.agents/skills/tutorial-gpt-recognition`：GPT-6.1-Sol / high，整页定位、完整棋图转录、严格契约校验、dry-run及TEST增量候选入库。
- 每位子智能体负责一本书，全局最多3个实际模型请求并行；每书每10个PDF页识别及校验完成后在session报告，尾批单独报告。
- 复用已完成final与原页、文字、缓存；不重跑OCR，不覆盖人工校准、审核或音视频。识别/机器检查与管理员人工审核分开。
- 仅TEST环境授权：home-ubuntu，DB system_identifier `7596941912817897507`，`katrain_db`，s3 `tutorial-assets`，媒体地址 `https://go.sailorvoyage.top/media`。不写生产或全表同步。
- 本轮不自动批量生成语音/视频；两阶段在HTML表中独立跟踪。

## 当前已核实进度

| 书名 | 棋图识别 | 验证 / 入库 |
| --- | --- | --- |
{rows}

“待开始”只代表本轮未开展；旧媒体未核对时不会写成不存在。石田书已完成195页/468图；已保留前100页最终266图及第92页修正。新自动结果不得标成人工审核通过。

## 现有可操作后台

- [测试教程后台](http://127.0.0.1:18012/admin?book=4&page=11&figure=1030&filter=all)，沿用现有SSH隧道和后台登录。
- 最新双档样例：第11页两图，各有Galaxy原生4K与RK1024×600版；新视频待人工审核。TEST provider `f671f20f6`，console `03e967a1`。普通消费者/RK实机未在本阶段部署。

## 当前工具与写入边界

识别使用包含最新实现的APP工作树：`/Users/fan/.config/superpowers/worktrees/katrain-tutorial-module/tutorial-workbench-2026-10-14`：

- `scripts/recognize_tutorial_book.py`：单书与10页检查点；数据输出在书籍仓库 `curriculum/recognition-comparison/curriculum-gpt61sol-v1/<catalog-id>/`。
- `scripts/import_tutorial_book_recognition.py`：通用整书TEST导入，先dry-run；旧石田专用CLI继续保留冻结守卫。
- 缺源PNG页只有确认无图、无来源引用的补渲染页可仅进入覆盖ledger；有图/有引用的页必须核对来源页注册与哈希后才入库。
- 每本交付覆盖/疑点/异常清单、来源到数据库ID映射、真实后台入口和独立SGF导出；顺序未知的静态图不编造replay。

## 更新方式

在本仓库运行 `python3 superpowers/tracks/tutorial-database/update_progress.py --refresh` 从识别输出刷新表格及本说明。每本识别完成必须执行一次；语音/视频阶段变化可用 `--book <catalog-id> --voice '<阶段>' --video '<阶段>'` 更新。原始书目来源：`/Users/fan/Repositories/go-topic-collections/docs/go-curriculum.html`；此仓库副本保留原模块、路径和书目内容。
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--output-root',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--book')
    for field in ('recognition','validation-import','human-review','voice','video'):
        parser.add_argument('--'+field)
    args = parser.parse_args()
    lock_path = Path('/tmp') / ('tutorial-progress-' + hashlib.sha256(str(HERE).encode()).hexdigest()[:16] + '.lock')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        data = json.loads((HERE/'progress.json').read_text())
        if args.refresh:
            refresh(data,args.output_root)
        if args.book:
            book = next((b for b in data['books'] if b['catalog_id']==args.book),None)
            if book is None:
                parser.error('unknown catalog id')
            for field in ('recognition','validation_import','human_review','voice','video'):
                value = getattr(args,field)
                if value is not None:
                    book[field] = value
                    if field == 'validation_import':
                        book['validation_import_manually_set'] = True
            book['updated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
        path = HERE/'go-curriculum.html'
        content = path.read_text()
        if content.count(START)!=1 or content.count(END)!=1:
            raise ValueError('unique progress markers required')
        first, rest = content.split(START,1)
        _, last = rest.split(END,1)
        (HERE/'progress.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        path.write_text(first+START+'\n'+table(data)+'\n'+END+last)
        (HERE/'plan.md').write_text(render_plan(data))
        print(f'Updated {len(data["books"])} book stages; original curriculum content retained.')


if __name__=='__main__':
    main()
