#!/usr/bin/env python3
"""Per-move summary of the RK3562 vision log (smartbox-katrain journal, short-iso-precise).

Usage: tail -n +1 -F game.log | python3 -u summarize.py [START_ISO]
Only events at/after START_ISO are printed (state is still built from the whole file).
One line per round (human move + the AI move placed by LED guidance); refcheck activity,
ambiguity, stalls and warnings are printed on their own immediately.
"""
import re
import sys
import statistics
from datetime import datetime

START = sys.argv[1] if len(sys.argv) > 1 else "0000"
LINE = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+)\S*\s+\S+\s+(\S+?)(?:\[\d+\])?:\s(.*)$")
CELL = re.compile(r"\((\d+),(\d+)\)([BW])~")
COLOR = {1: "黑", 2: "白"}
seen = set()


def ts(s):
    return datetime.strptime(s[:26], "%Y-%m-%dT%H:%M:%S.%f")


def hhmmss(t):
    return t.strftime("%H:%M:%S")


def gtp(r, c):  # vision row 0 = top edge (19 - r), columns skip I
    return "ABCDEFGHJKLMNOPQRST"[c] + str(19 - r)


class Round:
    def __init__(self):
        self.reset()

    def reset(self):
        self.first_add = {}  # (r,c,colour) -> first time it appeared in a board delta
        self.board_lost = 0
        self.lost_max = 0
        self.mass_occl = 0
        self.flicker = 0
        self.vt_total = []
        self.vt_ref = []
        self.ref_paused_drops = 0
        self.ref_events = []
        self.captures = 0
        self.human = None  # dict
        self.ai = None
        self.illegal_routine = 0


R = Round()
game_move = 0
led_on_at = None
led_cells = 0
glow = None
pending_at = {}
confirmed = None
ref_episode = None  # dict while refcheck keeps reporting
last_conf = None  # ((r,c), t) of the latest confirmed move
illegal_rep = {}  # body -> [last emitted t, repeats since]
illegal_buf = {}  # (r,c) -> (t, msg): single-stone illegal_change waiting for that cell's confirmation
live = False
all_ref = []
all_total = []
warn_seen = {}


def out(t, msg):
    if live:
        print(f"{hhmmss(t)} {msg}", flush=True)


def close_episode(t):
    global ref_episode
    e = ref_episode
    if not e:
        return
    ref_episode = None
    cells = ", ".join(sorted(e["cells"]))[:160]
    dur = (e["last"] - e["first"]).total_seconds()
    kinds = []
    if e["fn"]:
        kinds.append(f"棋谱有子/识别为空 {e['fn']} 次")
    if e["fp"]:
        kinds.append(f"棋谱为空/识别有子 {e['fp']} 次")
    if e["col"]:
        kinds.append(f"颜色不一致 {e['col']} 次")
    out(t, f"【参照帧】介入结束：{e['frames']} 帧 / {dur:.1f}s，最多 {e['max']} 格，{'; '.join(kinds)}；格子(每帧日志只列前4) {cells}")
    R.ref_events.append(e)


def round_line(t):
    h, a = R.human, R.ai
    parts = []
    if h:
        lat = f"{h['lat']:.1f}s" if h["lat"] is not None else "?"
        parts.append(
            f"第{h['n']}手 {COLOR.get(h['color'], h['color'])} {gtp(h['r'], h['c'])}({h['r']},{h['c']}) "
            f"落下→确认 {lat}（{h['obs']}/{h['req']}帧, 置信 {h['conf']}{', 可疑' + h['susp'] if h['susp'] != '0' else ''}）"
        )
    if a:
        parts.append(
            f"AI 第{a['n']}手 {gtp(a['r'], a['c'])} 亮灯→摆好 {a['lat']:.1f}s"
            + (f"（灯光 score {a['score']}, 亮度 {a['bright']}）" if a.get("score") else "")
        )
    extra = []
    if R.captures:
        extra.append(f"提子 {R.captures} 次")
    if R.board_lost:
        extra.append(f"手臂遮挡丢盘 {R.board_lost} 次(最多 {R.lost_max} 格)")
    elif R.mass_occl:
        extra.append(f"大片遮挡 {R.mass_occl} 次")
    if R.flicker:
        extra.append(f"单格闪烁 {R.flicker}")
    ref_frames = [x for x in R.vt_ref if x > 0]
    if R.vt_total:
        extra.append(
            (f"refchk 中位 {statistics.median(ref_frames):.0f}ms 峰 {max(ref_frames):.0f}ms（{len(ref_frames)}帧）" if ref_frames else "refchk 无")
            + f" / 帧中位 {statistics.median(R.vt_total):.0f}ms"
        )
    if R.ref_events:
        extra.append(f"参照帧介入 {len(R.ref_events)} 段")
    else:
        extra.append("参照帧未介入")
    out(t, " | ".join(parts + extra))
    for cell, (t0, m0) in list(illegal_buf.items()):
        if (t - t0).total_seconds() > 10:
            out(t0, f"⚠ 盘面不一致且没被确认成落子(illegal_change)：{m0.split('data=', 1)[1][:160]}")
            del illegal_buf[cell]
    R.reset()


def handle(t, src, msg):
    global game_move, led_on_at, led_cells, glow, confirmed, ref_episode, live, last_conf
    if not live and t.isoformat() >= START:
        live = True
    if ref_episode and (t - ref_episode["last"]).total_seconds() > 2.5 and "refcheck" not in msg:
        close_episode(t)

    if src == "systemd" or src.startswith("systemd"):
        if "smartbox-katrain" in msg and re.search(r"Stopp|Started|exited|Failed|Killed", msg):
            out(t, f"⚠ 服务状态：{msg[:160]}（重启后 vtrace 开关会丢）")
        return
    if "vtrace" in msg:
        m = re.search(r"total=(\d+).*?refchk=(\d+)", msg)
        if m:
            R.vt_total.append(int(m.group(1)))
            R.vt_ref.append(int(m.group(2)))
            all_total.append(int(m.group(1)))
            all_ref.append(int(m.group(2)))
        return
    if "Clock started for session" in msg:
        game_move = 0
        R.reset()
        out(t, "▶ 新对局开始（识别已绑定）")
        return
    if "board delta:" in msg:
        plus, _, minus = msg.partition("] -[")
        adds = CELL.findall(plus)
        rems = CELL.findall(minus)
        for r, c, col in adds:
            R.first_add.setdefault((int(r), int(c), col), t)
        if len(rems) >= 4:
            R.mass_occl += 1
        elif len(adds) + len(rems) <= 2:
            R.flicker += len(adds) + len(rems)
        return
    if "move_pending data=" in msg:
        m = re.search(r"'row': (\d+), 'col': (\d+), 'color': (\d+)", msg)
        if m:
            pending_at[(int(m.group(1)), int(m.group(2)))] = t
        return
    m = re.search(r"move confirmed: \((\d+),(\d+)\) color=(\d+) peak_conf=([\d.]+) required_frames=(\d+) observed_frames=(\d+) suspicion=(\S+)", msg)
    if m:
        r, c, color = int(m.group(1)), int(m.group(2)), int(m.group(3))
        colch = "B" if color == 1 else "W"
        first = R.first_add.get((r, c, colch))
        if illegal_buf.pop((r, c), None):
            R.illegal_routine += 1
        last_conf = ((r, c), t)
        confirmed = dict(
            r=r, c=c, color=color, conf=m.group(4), req=m.group(5), obs=m.group(6), susp=m.group(7),
            lat=(t - first).total_seconds() if first else None, at=t,
        )
        return
    if "Vision move submitted" in msg:
        game_move += 1
        if confirmed:
            confirmed["n"] = game_move
            R.human = confirmed
        confirmed = None
        return
    if "illegal_change data=" in msg:
        m1 = re.search(r"'positions': \[\((\d+), (\d+), \d+\)\], 'missing': \[\]", msg)
        if m1:
            cell = (int(m1.group(1)), int(m1.group(2)))
            if (confirmed and (confirmed["r"], confirmed["c"]) == cell) or (
                last_conf and last_conf[0] == cell and (t - last_conf[1]).total_seconds() < 15
            ):
                R.illegal_routine += 1
            else:
                illegal_buf[cell] = (t, msg)
        else:
            body = msg.split('data=', 1)[1][:200]
            prev = illegal_rep.get(body)
            if prev is None or (t - prev[0]).total_seconds() > 60:
                n = prev[1] if prev else 0
                out(t, f"⚠ 盘面不一致(illegal_change)：{body}" + (f"（此前 60s 内重复 {n} 次）" if n else ""))
                illegal_rep[body] = [t, 0]
            else:
                prev[1] += 1
        return
    if "board_lost data=" in msg:
        R.board_lost += 1
        m = re.search(r"diff_count': (\d+)", msg)
        if m:
            R.lost_max = max(R.lost_max, int(m.group(1)))
        return
    if "capture_pending" in msg:
        R.captures += 1
        out(t, f"· 提子：{msg.split('data=', 1)[1][:160] if 'data=' in msg else msg[:160]}")
        return
    if re.search(r"ambiguous_stone|degraded|game_end|physical_engine_error|\] error data", msg):
        out(t, f"⚠ {msg[:220]}")
        return
    m = re.search(r"\[DIAG-LED\] submit (\d+) leds", msg)
    if m:
        k = int(m.group(1))
        if k > 0 and led_on_at is None:
            led_on_at, led_cells = t, k
        elif k == 0 and led_on_at is not None:
            if glow:
                game_move += 1
                R.ai = dict(n=game_move, r=glow["r"], c=glow["c"], lat=(t - led_on_at).total_seconds(),
                            score=glow["score"], bright=glow["bright"])
                round_line(t)
            led_on_at, glow = None, None
        return
    m = re.search(r"LED glow at \((\d+),(\d+)\): ok=(\w+) score=(\d+).*?area=(\d+).*?brightness ([\d.]+ -> [\d.]+)", msg)
    if m:
        glow = dict(r=int(m.group(1)), c=int(m.group(2)), score=f"{m.group(4)}/面积{m.group(5)}", bright=m.group(6))
        return
    if "refcheck" in msg:
        if "reference dropped: paused" in msg:
            R.ref_paused_drops += 1
            return
        m = re.search(r"refcheck (?:would keep|keeps) (\d+) cell\(s\): (.*)", msg)
        if m:
            n = int(m.group(1))
            cells = re.findall(r"\((\d+),(\d+)\) board=(\d) ref=(\d) zncc=([\d.-]+) held=(\d+)/(\d+)", m.group(2))
            if ref_episode is None:
                ref_episode = dict(first=t, last=t, frames=0, max=0, cells=set(), fn=0, fp=0, col=0)
                out(t, f"【参照帧】开始介入 {n} 格：{m.group(2)[:220]}")
            e = ref_episode
            e["last"], e["frames"], e["max"] = t, e["frames"] + 1, max(e["max"], n)
            for r, c, b, rf, z, h, lim in cells:
                e["cells"].add(f"{gtp(int(r), int(c))}(b{b}/r{rf})")
                if b == "0" and rf != "0":
                    e["fn"] += 1
                elif b != "0" and rf == "0":
                    e["fp"] += 1
                else:
                    e["col"] += 1
            return
        out(t, f"【参照帧】{msg[msg.find('refcheck'):][:220]}")
        return
    if msg.startswith(("W:", "E:", "WARNING", "ERROR", "CRITICAL")) or "Traceback" in msg:
        key = re.sub(r"\d+", "#", msg[:80])
        cnt = warn_seen.get(key, 0) + 1
        warn_seen[key] = cnt
        if cnt <= 2 or cnt in (10, 100):
            out(t, f"⚠ 日志告警({cnt}): {msg[:220]}")
        return


for raw in sys.stdin:
    if raw in seen:
        continue
    seen.add(raw)
    mm = LINE.match(raw.rstrip("\n"))
    if not mm:
        continue
    try:
        handle(ts(mm.group(1)), mm.group(2), mm.group(3))
    except Exception as exc:  # never let one odd line kill the monitor
        print(f"[summarize] parse error: {exc}: {raw[:120]}", flush=True)
