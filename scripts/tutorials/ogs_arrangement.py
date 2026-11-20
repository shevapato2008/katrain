"""Assemble frozen OGS selections using the already captured, current TEST media.

Standard library only. This command reads local JSON and writes local review artifacts;
it never captures remote data, publishes a manifest, or generates/downloads media.
"""

import argparse
import csv
import hashlib
import html
import json
import math
import re
from pathlib import Path
from urllib.parse import quote


VERSION = "ogs-video-arrangement-2026-11-17"
MEDIA_BASE = "https://go.sailorvoyage.top/media/"
PROFILES = {"kiosk-7-v1": (1024, 600), "galaxy-4k-v1": (3840, 2160)}
PIN_FIELDS = (
    "book_id",
    "page",
    "figure_label",
    "book_text",
    "narration",
    "narration_sha256",
    "board_sha256",
    "source_identity",
    "audio",
    "profiles",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def keyed(rows, key, label):
    result = {}
    for row in rows:
        value = row[key]
        require(value not in result, f"duplicate {label}: {value}")
        result[value] = row
    return result


def required_text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"missing {label}")
    return value.strip()


def positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def load_pinned_index(data_dir):
    """Refuse a locally edited/unpinned index before any artifacts are written."""
    data_dir = Path(data_dir)
    proof = read_json(data_dir / "capture-proof.json")
    raw = (data_dir / "video-index.json").read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == proof.get("index_sha256"), "video-index checksum differs from capture-proof"
    )
    require(proof.get("index_bytes", len(raw)) == len(raw), "video-index byte count differs from capture-proof")
    return json.loads(raw), proof


def validate_media(video_index, capture, proof, final_report):
    require(proof.get("environment") == "TEST", "capture-proof must identify TEST")
    require(proof.get("source_board_audio_asset_pins_matched") is True, "current source/media pins were not verified")
    identity = proof.get("identity")
    require(
        bool(identity) and identity == video_index.get("identity") == capture.get("identity"), "TEST identity mismatch"
    )
    require(video_index.get("captured_at") == capture.get("captured_at"), "capture timestamp mismatch")
    clips = keyed(video_index["clips"], "id", "video ID")
    current = keyed(capture["clips"], "id", "capture ID")
    require(
        len(clips) == len(current) == proof.get("clips") == final_report.get("current_complete_figures") == 1931,
        "expected exactly 1931 current completed clips",
    )
    require(set(clips) == set(current), "index/current-capture IDs differ")
    excluded = {row["figure_id"] for row in final_report["scope_exclusions"]}
    require(len(excluded) == len(final_report["scope_exclusions"]) == 15, "expected exactly 15 source exclusions")
    require(not excluded.intersection(clips), "excluded clip is present in current index")
    for figure_id, clip in clips.items():
        require(type(figure_id) is int and figure_id > 0, "video ID must be a positive integer")
        for field in PIN_FIELDS:
            require(field in clip and clip[field] == current[figure_id].get(field), f"stale clip {figure_id}: {field}")
        require(positive_number(clip["audio"].get("duration_ms")), f"missing audio duration: {figure_id}")
        require(set(clip.get("profiles", {})) == set(PROFILES), f"missing/unsupported profile: {figure_id}")
        for profile, (width, height) in PROFILES.items():
            asset = clip["profiles"][profile]
            pattern = rf"tutorial_assets/[a-z0-9-]+/media/[0-9a-f]{{32}}/video-2d-{re.escape(profile)}\.mp4"
            require(
                isinstance(asset.get("asset"), str) and re.fullmatch(pattern, asset["asset"]),
                f"invalid immutable asset path: {figure_id}/{profile}",
            )
            require(
                (asset.get("width"), asset.get("height")) == (width, height),
                f"invalid dimensions: {figure_id}/{profile}",
            )
            require(positive_number(asset.get("duration_ms")), f"missing video duration: {figure_id}/{profile}")
            require(asset.get("timing_status") == "complete", f"incomplete timing: {figure_id}/{profile}")
            require(
                isinstance(asset.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", asset["sha256"]),
                f"missing asset fingerprint: {figure_id}/{profile}",
            )
    return clips, excluded


def source_reference(unit, clip):
    require(
        unit["book_id"] == clip["book_id"] and unit["catalog_id"] == clip["catalog_id"],
        f"source book mismatch: {clip['id']}/{unit['id']}",
    )
    pages = unit["pdf_pages"]
    require(
        len(pages) == 2 and pages[0] <= clip["page"] <= pages[1], f"source page mismatch: {clip['id']}/{unit['id']}"
    )
    pdf = required_text(unit.get("pdf"), f"PDF for {unit['id']}")
    require(Path(pdf).is_absolute(), f"PDF path must be absolute: {unit['id']}")
    return {
        "id": unit["id"],
        "book_id": unit["book_id"],
        "catalog_id": unit["catalog_id"],
        "book_title": unit["book_title"],
        "chapter": unit.get("chapter", ""),
        "section": unit.get("section", ""),
        "pdf_pages": pages,
        "pdf_url": Path(pdf).as_uri() + f"#page={clip['page']}",
        "selection_note": unit.get("selection_note", ""),
    }


def assemble(
    *, outline, goals, video_index, capture, proof, final_report, contract, baseline_manifest, chapter_documents
):
    """Validate all editorial rows, then return the review document and player manifest."""
    lessons = keyed(outline["lessons"], "id", "outline lesson")
    lesson_goals = keyed(goals["lessons"], "id", "goal lesson")
    require(
        len(lessons) == 248 and set(lessons) == set(lesson_goals), "lesson goal coverage must exactly match 248 OGS IDs"
    )
    units = outline["source_units"]
    units = keyed(units, "id", "source unit") if isinstance(units, list) else units
    clips, excluded = validate_media(video_index, capture, proof, final_report)
    require(contract.get("schema_version") == 1, "unsupported editorial contract")
    baseline = baseline_manifest["playlists"]
    require(
        len(baseline) == 14 and baseline == contract.get("baseline_playlists"),
        "original 14 baseline playlists differ from contract",
    )
    require(set(baseline).issubset(lessons), "baseline references unknown lesson")
    baseline_titles = {
        clip["id"]: required_text(clip.get("title"), f"baseline clip {clip['id']} title")
        for clip in baseline_manifest["clips"]
    }
    decisions = []
    for document in chapter_documents:
        require(document.get("schema_version") == 1, "unsupported chapter schema")
        for row in document["lessons"]:
            require(
                row.get("lesson_id") not in lessons
                or document["chapter_number"] == lessons[row["lesson_id"]]["chapter_number"],
                f"wrong chapter: {row.get('lesson_id')}",
            )
            decisions.append(row)
    decisions = keyed(decisions, "lesson_id", "lesson")
    require(
        set(decisions) == set(lessons),
        f"lesson coverage differs: missing={sorted(set(lessons) - set(decisions))}, unknown={sorted(set(decisions) - set(lessons))}",
    )
    rows, manifest_clips, playlists = [], {}, {}
    roles = set(contract.get("role_values", ["概念", "示范", "对照", "巩固"]))
    for lesson_id, lesson in lessons.items():
        row = decisions[lesson_id]
        require(row.get("course_code") == lesson["course_code"], f"course_code mismatch: {lesson_id}")
        text = {
            field: required_text(row.get(field), f"{lesson_id}/{field}")
            for field in ("goal", "intro", "practice_bridge")
        }
        notes = row.get("coverage_notes")
        require(
            isinstance(notes, list) and all(isinstance(x, str) and x.strip() for x in notes),
            f"invalid coverage_notes: {lesson_id}",
        )
        selections = row.get("clips")
        require(isinstance(selections, list) and bool(selections), f"empty playlist: {lesson_id}")
        sequence = [selection["figure_id"] for selection in selections]
        require(len(sequence) == len(set(sequence)), f"duplicate clip in playlist: {lesson_id}")
        if lesson_id in baseline:
            require(sequence == baseline[lesson_id], f"baseline playlist/order changed: {lesson_id}")
        selected = []
        for position, selection in enumerate(selections, 1):
            figure_id = selection["figure_id"]
            require(
                type(figure_id) is int and figure_id not in excluded, f"excluded/invalid clip: {lesson_id}/{figure_id}"
            )
            require(figure_id in clips, f"unknown current clip: {lesson_id}/{figure_id}")
            clip = clips[figure_id]
            require(selection.get("role") in roles, f"invalid clip role: {lesson_id}/{figure_id}")
            focus = required_text(selection.get("focus"), f"{lesson_id}/{figure_id}/focus")
            rationale = required_text(selection.get("rationale"), f"{lesson_id}/{figure_id}/rationale")
            unit_id = selection.get("source_unit")
            require(
                unit_id in units and unit_id in clip["source_units"], f"invalid source_unit: {lesson_id}/{figure_id}"
            )
            source = source_reference(units[unit_id], clip)
            profiles = {
                name: {"url": MEDIA_BASE + asset["asset"], "width": asset["width"], "height": asset["height"]}
                for name, asset in clip["profiles"].items()
            }
            durations = {name: asset["duration_ms"] / 1000 for name, asset in clip["profiles"].items()}
            duration = durations["kiosk-7-v1"]
            title = f"{clip['book_title']} · PDF {clip['page']} · {clip['figure_label'] or '图' + str(figure_id)}"
            manifest_clips.setdefault(
                figure_id,
                {
                    "id": figure_id,
                    "title": baseline_titles.get(figure_id, focus),
                    "book": clip["book_title"],
                    "page": clip["page"],
                    "duration": duration,
                    "profiles": profiles,
                },
            )
            selected.append(
                {
                    "position": position,
                    "figure_id": figure_id,
                    "title": title,
                    "role": selection["role"],
                    "focus": focus,
                    "rationale": rationale,
                    "source_unit": unit_id,
                    "source": source,
                    "book_id": clip["book_id"],
                    "book_title": clip["book_title"],
                    "catalog_id": clip["catalog_id"],
                    "page": clip["page"],
                    "figure_label": clip["figure_label"],
                    "duration_seconds": duration,
                    "duration_by_profile": durations,
                    "profiles": profiles,
                    "admin_url": f"http://127.0.0.1:18012/admin?book={clip['book_id']}&page={clip['page']}&figure={figure_id}&filter=all",
                    "context_flags": clip.get("context_flags", []),
                    "current_media_pins": {
                        "narration_sha256": clip["narration_sha256"],
                        "board_sha256": clip["board_sha256"],
                        "source_identity": clip["source_identity"],
                        "audio": {key: clip["audio"][key] for key in ("asset", "sha256", "duration_ms")},
                        "profiles": {
                            name: {key: asset[key] for key in ("asset", "sha256", "duration_ms")}
                            for name, asset in clip["profiles"].items()
                        },
                    },
                }
            )
        playlists[lesson_id] = sequence
        rows.append(
            {
                "lesson_id": lesson_id,
                "course_code": lesson["course_code"],
                "title": lesson["title"],
                "chapter_id": lesson["chapter_id"],
                "chapter_number": lesson["chapter_number"],
                "chapter_title": lesson["chapter_title"],
                "step_count": lesson["step_count"],
                "ogs_goal": lesson_goals[lesson_id]["topic_summary"],
                "ogs_instructions": [
                    {"step": step["step"], "instruction": step["instruction"]}
                    for step in lesson_goals[lesson_id]["steps"]
                ],
                "ogs_url": "https://online-go.com/learn-to-play-go/" + quote(lesson_id, safe=""),
                **text,
                "coverage_notes": notes,
                "clips": selected,
                "duration_seconds": round(sum(clip["duration_seconds"] for clip in selected), 3),
                "duration_by_profile": {
                    name: round(sum(clip["duration_by_profile"][name] for clip in selected), 3) for name in PROFILES
                },
                "test_association_status": "prepared_not_published",
                "prod_association_status": (
                    "existing_baseline_unchanged" if lesson_id in baseline else "not_associated_by_this_arrangement"
                ),
            }
        )
    manifest = {
        "schema_version": 1,
        "release_id": "ogs-full-test-20261117",
        "language": "zh-cn",
        "clips": list(manifest_clips.values()),
        "playlists": playlists,
    }
    track = {
        "schema_version": 1,
        "version": VERSION,
        "title": "OGS 248 小节视频编排",
        "status": "local_test_manifest_prepared",
        "captured_at": video_index["captured_at"],
        "media_environment": "TEST",
        "media_base": MEDIA_BASE,
        "publication": {
            "test": "prepared_not_published",
            "prod": "existing_14_unchanged",
            "note": "本地清单与审查表已准备；本次汇总不代表已发布、已挂载或设备验收。PROD既有14节片单未改。",
        },
        "validation": {
            "exact_248_ids": True,
            "current_1931_clips_pinned": True,
            "excluded_15_not_used": True,
            "all_selected_dual_profile": True,
            "baseline_14_preserved": True,
            "index_sha256": proof.get("index_sha256"),
            "test_identity": proof["identity"],
        },
        "counts": {
            "lessons": 248,
            "current_clips": 1931,
            "excluded_clips": 15,
            "baseline_lessons": 14,
            "unique_selected_clips": len(manifest_clips),
            "playlist_entries": sum(map(len, playlists.values())),
            "playlist_duration_seconds": round(sum(row["duration_seconds"] for row in rows), 3),
        },
        "baseline_playlists": baseline,
        "lessons": rows,
    }
    return track, manifest


def duration_label(seconds):
    total = round(seconds)
    return f"{total // 60}:{total % 60:02d}"


def render_html(track, output_name):
    """Paper/green curriculum styling; all media stays unloaded until explicit selection."""
    esc = html.escape
    chapters = {row["chapter_number"]: row["chapter_title"] for row in track["lessons"]}
    sources = {clip["catalog_id"]: clip["book_title"] for row in track["lessons"] for clip in row["clips"]}
    options = lambda items: "".join(
        f'<option value="{esc(str(key))}">{esc(str(value))}</option>' for key, value in items
    )
    rendered = []
    for row in track["lessons"]:
        clips = []
        for clip in row["clips"]:
            source = clip["source"]
            controls = " ".join(
                f'<button type="button" class="preview" data-src="{esc(clip["profiles"][profile]["url"])}" '
                f'data-local-src="/preview-media/{clip["figure_id"]}/{profile}.mp4" '
                f'data-title="{esc(clip["title"] + " · " + label)}">选择{label}</button>'
                for profile, label in (("kiosk-7-v1", "kiosk 7英寸"), ("galaxy-4k-v1", "Galaxy 4K"))
            )
            flags = (
                f'<p class="muted">讲稿上下文提示：{esc("、".join(clip["context_flags"]))}</p>'
                if clip["context_flags"]
                else ""
            )
            clips.append(
                f'<li><h3>{clip["position"]}. {esc(clip["role"])} · {esc(clip["focus"])}</h3>'
                f'<p>{esc(clip["rationale"])}</p><p class="source-line"><span class="pdf-page">'
                f'{esc(clip["book_title"])} · PDF {clip["page"]}</span> · '
                f'<a class="pdf-local-link" href="{esc(source["pdf_url"])}" target="_blank" rel="noopener">原书PDF</a>'
                f'<span class="pdf-http-note" hidden>PDF页码已列，可从原书/管理后台核对</span> · {esc(clip["figure_label"] or "图")}'
                f' #{clip["figure_id"]} · <a href="{esc(clip["admin_url"])}" target="_blank" rel="noopener">Admin原图</a></p>'
                f'<p class="muted">{esc(source["chapter"])} / {esc(source["section"])} · {esc(source["id"])} '
                f'（来源PDF {source["pdf_pages"][0]}–{source["pdf_pages"][1]}）</p>{flags}'
                f'<p class="source-line">kiosk {duration_label(clip["duration_by_profile"]["kiosk-7-v1"])} · '
                f'4K {duration_label(clip["duration_by_profile"]["galaxy-4k-v1"])} · 实测 {clip["duration_seconds"]:.3f} 秒</p>'
                f'<div class="clip-actions">{controls}</div></li>'
            )
        notes = "".join(f"<li>{esc(note)}</li>" for note in row["coverage_notes"])
        instruction = "".join(
            f'<li>{step["step"]}. {esc(step["instruction"])}</li>' for step in row["ogs_instructions"]
        )
        searchable = " ".join(
            [
                row["lesson_id"],
                row["title"],
                row["course_code"],
                row["goal"],
                row["ogs_goal"],
                row["intro"],
                row["practice_bridge"],
                *row["coverage_notes"],
                *(clip["book_title"] + " " + clip["focus"] + " " + clip["rationale"] for clip in row["clips"]),
            ]
        )
        source_ids = " ".join(sorted({clip["catalog_id"] for clip in row["clips"]}))
        baseline = "既有PROD基线 · 顺序保留" if row["lesson_id"] in track["baseline_playlists"] else "本轮新增编排"
        sequence = " → ".join(f'#{clip["figure_id"]} {clip["focus"]}' for clip in row["clips"])
        rendered.append(
            f'<tr class="lesson-row" id="lesson-{esc(row["lesson_id"])}" data-chapter="{row["chapter_number"]}" '
            f'data-source="{esc(source_ids)}" data-search="{esc(searchable.lower())}">'
            f'<th scope="row"><span class="course-code">{esc(row["course_code"])} · 第{row["chapter_number"]}章 {esc(row["chapter_title"])}</span>'
            f'<h3>{esc(row["title"])}</h3><p class="muted">{esc(row["lesson_id"])}</p><p class="badge">{baseline}</p>'
            f'<p><a href="{esc(row["ogs_url"])}" target="_blank" rel="noopener">OGS原练习 · {row["step_count"]}步</a></p>'
            f'<p><a class="lesson-preview-link" href="/kiosk/tutorial/lesson/{quote(row["lesson_id"], safe="")}/videos" target="_blank" rel="noopener">试学本节：视频 → 练习 ↗</a></p></th>'
            f'<td><p>{esc(row["goal"])}</p><p class="muted">原练习：{esc(row["ogs_goal"])}</p></td>'
            f'<td><details><summary>{len(row["clips"])}段 · 展开片序、来源与导读</summary><p class="sequence">{esc(sequence)}</p>'
            f'<div class="note"><strong>导读</strong><p>{esc(row["intro"])}</p><strong>进入练习</strong><p>{esc(row["practice_bridge"])}</p></div>'
            f'<ol class="clips">{"".join(clips)}</ol><div class="coverage"><strong>覆盖说明</strong><ul>{notes}</ul></div>'
            f'<details class="instructions"><summary>原OGS步骤说明</summary><ul>{instruction}</ul></details></details></td>'
            f'<td><strong class="duration">{duration_label(row["duration_seconds"])}</strong><p class="muted">{row["duration_seconds"]:.3f}秒</p>'
            f'<span class="badge">TEST清单已准备</span><p class="muted">待发布 / 待运行验证</p></td></tr>'
        )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OGS 248 小节视频编排</title><style>{CSS}</style></head><body>
<a class="skip" href="#lessons">跳到编排表</a><header class="topbar"><div class="shell"><a class="brand" href="go-curriculum.html">围棋教材课程</a>
<a class="lesson-preview-link" href="/kiosk/tutorial">打开TEST试学</a><a href="ogs-video-outline-2026-11-12.html">原选材提纲</a></div></header><main class="shell">
<section class="hero"><p class="eyebrow">OGS · 2026.11.17 · TEST素材编排</p><h1>先看懂，再落子。</h1>
<p class="desc">沿现有七章、248小节，为每节选择有序视频，再衔接本节OGS练习。展开查看选片理由、原书PDF页码与两档现成视频。</p></section>
<div class="stats"><div><strong>248</strong><p>小节完整编排</p></div><div><strong>{track["counts"]["unique_selected_clips"]}</strong><p>本轮采用现成图段</p></div>
<div><strong>1,931</strong><p>当前可用双档素材</p></div><div><strong>14</strong><p>PROD基线片单保留</p></div></div>
<div class="note"><strong>TEST片单已准备 · 正式环境尚未发布</strong><p>{esc(track["publication"]["note"])}</p>
<p>素材来自已固定的TEST成品索引；15个排除项未参与。每段时长取自现有MP4元数据。选编不等于逐题内容完全覆盖，边界见各节说明。</p>
<p>点击“选择”后才装入所选档位，随后可使用视频控件播放。页面打开时不请求媒体。</p></div>
<section id="lessons"><h2>逐节片单与来源</h2><div class="filters"><div class="filter-grid">
<label>关键词<input id="search" type="search" placeholder="小节、目标、选片理由或书名"></label>
<label>章节<select id="chapter"><option value="">全部章节</option>{options(chapters.items())}</select></label>
<label>来源教材<select id="source"><option value="">全部来源</option>{options(sorted(sources.items()))}</select></label>
<button id="reset" type="button">重置</button></div><p id="result" aria-live="polite">显示248 / 248小节</p></div>
<div class="table-wrap"><table><thead><tr><th scope="col">OGS小节</th><th scope="col">本节目标</th><th scope="col">视频片序 / 教学衔接</th><th scope="col">实际总时长 / 状态</th></tr></thead>
<tbody>{"".join(rendered)}</tbody></table><p id="empty" hidden>没有符合条件的小节。</p></div></section>
<footer><a href="{esc(output_name)}.json">结构化编排JSON</a> · <a href="{esc(output_name)}.csv">完整CSV</a>
<p>PDF均为从1开始的物理页码。Admin链接沿用本机TEST后台地址。素材捕获：{esc(track["captured_at"])}</p></footer></main>
<dialog id="preview-dialog"><div class="dialog-head"><h2 id="preview-title">TEST视频预览</h2><button id="close-preview" type="button">关闭</button></div>
<p class="muted">使用下方控件开始播放；可关闭后选择另一档位。</p><video id="preview-video" controls preload="none" playsinline></video></dialog>
<script>{JAVASCRIPT}</script></body></html>"""


CSS = """
:root{--paper:#f5f1e7;--surface:#fffdf7;--ink:#22332b;--muted:#63685f;--line:#d9dbcc;--green:#214f40;--green-light:#e8eee4;--clay:#8d5b36;--serif:"Songti SC","STSong",serif;--sans:"PingFang SC","Microsoft YaHei",sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.75 var(--sans)}a{color:var(--green);text-underline-offset:4px}h1,h2,h3,p{margin:0}h1,h2{font-family:var(--serif)}h1{font-size:clamp(32px,3.8vw,52px);line-height:1.3;margin:15px 0 20px}h2{font-size:26px}h3{font-size:16px}.shell{max-width:1580px;margin:auto;padding:0 32px}.topbar{border-bottom:1px solid var(--line)}.topbar .shell{display:flex;justify-content:space-between;gap:20px;padding-top:16px;padding-bottom:16px}.brand{font:700 20px var(--serif);text-decoration:none}.hero{padding:42px 0 28px;max-width:1080px}.eyebrow{color:var(--clay);font-size:12px;letter-spacing:.1em}.desc{font-size:17px;color:var(--muted)}.stats{display:grid;grid-template-columns:repeat(4,1fr);border-block:1px solid var(--line);margin-bottom:24px}.stats>div{padding:18px 24px;border-right:1px solid var(--line)}.stats>div:first-child{padding-left:0}.stats>div:last-child{border:0}.stats strong{font:36px/1.3 var(--serif);color:var(--green)}.stats p,.muted{color:var(--muted);font-size:13px}.note{background:var(--green-light);padding:16px 20px;border-left:3px solid var(--green);margin:16px 0 24px}.note strong{color:var(--green)}.note p+p{margin-top:8px}.filters{position:sticky;top:0;z-index:2;background:var(--paper);border-block:1px solid var(--line);padding:14px 0 10px;margin-top:18px}.filter-grid{display:grid;grid-template-columns:1fr 160px 260px auto;gap:12px;align-items:end}label{display:flex;flex-direction:column;font-size:12px;color:var(--muted);gap:5px}button,input,select{font:inherit}button,input,select{min-height:44px;padding:8px 12px;background:var(--surface);border:1px solid var(--line);border-radius:5px;color:var(--ink);min-width:0}button,select,summary{cursor:pointer}button:hover{background:var(--green-light)}:focus-visible{outline:3px solid var(--clay);outline-offset:3px}#result{font-size:13px;color:var(--muted);margin-top:8px}.table-wrap{overflow-x:auto;border:1px solid var(--line);margin:18px 0;background:var(--surface)}table{width:100%;min-width:940px;border-collapse:collapse;table-layout:fixed;font-size:14px}thead{background:var(--green-light)}th,td{text-align:left;vertical-align:top;padding:18px 16px;border-bottom:1px solid var(--line);font-weight:400;overflow-wrap:anywhere}thead th:nth-child(1){width:20%}thead th:nth-child(2){width:28%}thead th:nth-child(3){width:39%}thead th:nth-child(4){width:13%}.course-code{display:block;color:var(--clay);font-size:12px;margin-bottom:5px}.badge{display:inline-block;font-size:12px;padding:3px 8px;background:var(--green-light);color:var(--green);border-radius:4px;margin:8px 0}.duration{display:block;font:26px var(--serif);color:var(--green)}summary{font-weight:600;color:var(--green);min-height:44px;padding:8px 0}.sequence{font-size:13px;padding-top:8px}.clips{padding-left:20px}.clips>li{padding:14px 0;border-top:1px solid var(--line)}.source-line{font-size:13px;margin-top:7px}.clip-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.clip-actions button{font-size:12px}.coverage{border-top:1px solid var(--line);padding-top:12px}.coverage ul,.instructions ul{padding-left:20px}.instructions{margin-top:12px}.instructions li{margin-bottom:8px}.lesson-row:hover{background:#fafaf1}footer{padding:20px 0 36px;font-size:13px;color:var(--muted)}dialog{max-width:min(1000px,calc(100vw - 32px));width:100%;padding:20px;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:8px}dialog::backdrop{background:#22332b88}.dialog-head{display:flex;justify-content:space-between;gap:20px;align-items:center}.dialog-head h2{font:18px var(--sans)}video{display:block;width:100%;max-height:72vh;margin-top:12px;background:#000}.skip{position:absolute;left:16px;top:-80px}.skip:focus{top:12px;z-index:10;background:white;padding:8px}[hidden]{display:none!important}#empty{text-align:center;padding:32px}
@media(max-width:1050px){.shell{padding:0 20px}.filter-grid{grid-template-columns:1fr 150px 240px auto}th,td{padding:14px 12px}}@media(max-width:760px){.filter-grid{grid-template-columns:1fr 1fr}label:first-child{grid-column:1/-1}.stats{grid-template-columns:repeat(2,1fr)}.stats>div{padding:14px!important;border:0}.stats strong{font-size:30px}.hero{padding:28px 0}.topbar .shell{flex-wrap:wrap}dialog{padding:12px}.dialog-head h2{font-size:15px}}@media print{.topbar,.filters,.clip-actions,dialog{display:none}.shell{padding:0}.table-wrap{overflow:visible}table{min-width:0;font-size:10px}.hero{padding-top:0}h1{font-size:28px}th,td{padding:8px}.note{padding:10px}body{background:white}.stats strong{font-size:24px}}"""

JAVASCRIPT = """
const isHttpDocument=['http:','https:'].includes(location.protocol);
if(!isHttpDocument)document.querySelectorAll('.lesson-preview-link').forEach(link=>{link.href='http://127.0.0.1:18957'+link.getAttribute('href');});
document.querySelectorAll('.pdf-local-link').forEach(link=>{link.hidden=isHttpDocument;});
document.querySelectorAll('.pdf-http-note').forEach(note=>{note.hidden=!isHttpDocument;});
const rows=Array.from(document.querySelectorAll('.lesson-row'));
const search=document.getElementById('search'),chapter=document.getElementById('chapter'),source=document.getElementById('source');
function filter(){let count=0;const needle=search.value.trim().toLowerCase();for(const row of rows){const yes=(!needle||row.dataset.search.includes(needle))&&(!chapter.value||row.dataset.chapter===chapter.value)&&(!source.value||row.dataset.source.split(' ').includes(source.value));row.hidden=!yes;if(yes)count++;}document.getElementById('result').textContent=`显示${count} / 248小节`;document.getElementById('empty').hidden=count>0;}
search.addEventListener('input',filter);chapter.addEventListener('change',filter);source.addEventListener('change',filter);
document.getElementById('reset').addEventListener('click',()=>{search.value='';chapter.value='';source.value='';filter();});
const dialog=document.getElementById('preview-dialog'),video=document.getElementById('preview-video');
document.querySelectorAll('.preview').forEach(button=>button.addEventListener('click',()=>{video.pause();document.getElementById('preview-title').textContent=button.dataset.title;video.src=isHttpDocument?button.dataset.localSrc:button.dataset.src;dialog.showModal();}));
document.getElementById('close-preview').addEventListener('click',()=>dialog.close());
dialog.addEventListener('close',()=>{video.pause();video.removeAttribute('src');video.load();});
"""


def write_artifacts(track, manifest, data_dir, output_prefix):
    data_dir, output_prefix = Path(data_dir), Path(output_prefix)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {suffix: output_prefix.with_suffix("." + suffix) for suffix in ("json", "csv", "html")}
    paths["manifest"] = data_dir / "test-manifest.json"
    for path, payload in ((paths["json"], track), (paths["manifest"], manifest)):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "course_code",
        "lesson_id",
        "chapter_number",
        "chapter_title",
        "title",
        "goal",
        "ogs_goal",
        "intro",
        "practice_bridge",
        "duration_seconds",
        "coverage_notes",
        "ordered_clips",
        "ogs_url",
        "test_association_status",
        "prod_association_status",
    ]
    with paths["csv"].open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in track["lessons"]:
            record = {field: row[field] for field in fields if field not in {"coverage_notes", "ordered_clips"}}
            record["coverage_notes"] = " | ".join(row["coverage_notes"])
            record["ordered_clips"] = json.dumps(row["clips"], ensure_ascii=False, separators=(",", ":"))
            writer.writerow(record)
    paths["html"].write_text(render_html(track, output_prefix.name), encoding="utf-8")
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="local main worktree containing the prepared data"
    )
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--outline", type=Path)
    parser.add_argument("--final-report", type=Path)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--output-prefix", type=Path)
    parser.add_argument("--validate-only", action="store_true", help="validate without writing artifacts")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    batch = root / "data/tutorial_media_batches/ogs-book-sources-20261113"
    data_dir = args.data_dir or batch / "arrangement-20261117"
    track_dir = root / "superpowers/tracks/tutorial-database"
    try:
        video_index, proof = load_pinned_index(data_dir)
        chapter_paths = sorted((data_dir / "chapters").glob("chapter-*.json"))
        require(bool(chapter_paths), f"no completed chapter JSON files in {data_dir / 'chapters'}")
        track, manifest = assemble(
            outline=read_json(args.outline or track_dir / "ogs-video-outline-2026-11-12.json"),
            goals=read_json(data_dir / "lesson-goals.json"),
            video_index=video_index,
            capture=read_json(data_dir / "current-video-capture.json"),
            proof=proof,
            final_report=read_json(args.final_report or batch / "resume-full-20261117/final-report.json"),
            contract=read_json(data_dir / "editorial-contract.json"),
            baseline_manifest=read_json(
                args.baseline_manifest or track_dir / "demo-7inch-2026-11-15/production-manifest.json"
            ),
            chapter_documents=[read_json(path) for path in chapter_paths],
        )
        paths = (
            {}
            if args.validate_only
            else write_artifacts(track, manifest, data_dir, args.output_prefix or track_dir / VERSION)
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"Arrangement validation failed: {error}\n")
    print(
        json.dumps(
            {
                "status": "validated" if args.validate_only else "local_artifacts_prepared_not_published",
                "counts": track["counts"],
                "paths": {key: str(path) for key, path in paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
