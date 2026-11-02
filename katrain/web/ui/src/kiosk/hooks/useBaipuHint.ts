// 摆谱(屏 17)的 AI 支招:分析**谱上**第 k 手之后的局面,走本机 KataGo(`/analysis/quick-analyze`,无会话)。
// 分析的是谱,不是摄像头看到的盘 —— 支招开着时识别是暂停的(usePhysicalBaipu 的 PAUSE),两者本来就该一致。
//
// 候选点给三处用:右栏折叠块三行、盘上白圈(`GoBoardSvg` 的 `hint`)、实体盘白灯(`leds`,color 'hint')。
// 行为照对弈页的 AI 支招:30 s 自动收起(对弈 `hint_timeout_s = 30`)、再按一次收起、换了一手就收起。

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../../api';
import { canonToGtp, type BaipuMeta, type BaipuStep } from '../../api/baipuApi';
import { useAuth } from '../../context/AuthContext';
import { replayBaipuSteps } from '../../utils/baipuReplay';
import type { LedPoint } from './physicalBaipuMachine';

/** 已按走子方翻转(后端是黑方视角,`ResearchPage.toRows` 同口径)。 */
export interface HintRow { move: string; winrate: number; scoreLead: number }
export type HintStatus = 'idle' | 'loading' | 'ok' | 'error';
export interface BaipuHint {
  open: boolean;
  status: HintStatus;
  rows: HintRow[];
  leds: LedPoint[];
  toggle: () => void;
  close: () => void;
}

export const HINT_TIMEOUT_MS = 30_000;
const NO_ROWS: HintRow[] = [];
const GTP_COLS = 'ABCDEFGHJKLMNOPQRST';
type Color = 'B' | 'W';
const other = (c: Color): Color => (c === 'B' ? 'W' : 'B');
const recordedColor = (s: BaipuStep): Color | null => s.color
  ?? (s.kind === 'pass' && (s.property === 'B' || s.property === 'W') ? s.property : null);
const played = (s: BaipuStep) => (s.kind === 'move' || s.kind === 'pass') && !!recordedColor(s);

/** 轮谁走:从第 k 步往后第一手的颜色;摆到最后就取最后一手的反色;一手都没有取黑。 */
export function hintMover(steps: readonly BaipuStep[], k: number): Color {
  const ahead = steps.slice(k).find(played);
  if (ahead) return recordedColor(ahead) as Color;
  const behind = steps.slice(0, k).reverse().find(played);
  return behind ? other(recordedColor(behind) as Color) : 'B';
}

/** Detect record operations that KataGo's legal move list cannot reproduce. */
function needsPositionSnapshot(head: readonly BaipuStep[]): boolean {
  const occupied = new Set<string>();
  let sawPlayedMove = false;
  const key = (p: { row: number; col: number }) => `${p.row},${p.col}`;
  for (const s of head) {
    if (s.kind === 'clear' || s.pre_removed?.length) return true;
    if (s.kind === 'setup' && sawPlayedMove) return true;
    if (played(s)) sawPlayedMove = true;
    if (s.row != null && s.col != null && s.color) {
      const point = key({ row: s.row, col: s.col });
      if (occupied.has(point) || s.requires_placement === false
        || s.removed.some(p => key(p) === point)) return true;
      occupied.add(point);
    }
    for (const p of s.removed) occupied.delete(key(p));
  }
  return false;
}

export function buildHintRequest(steps: readonly BaipuStep[], k: number, size: number, meta: BaipuMeta | null) {
  const head = steps.slice(0, k);
  let moves: string[][];
  let initial_stones: string[][];
  if (needsPositionSnapshot(head)) {
    // Record operations and setup after play cannot be reordered into legal
    // history. Analyze the authoritative current board instead.
    const b = replayBaipuSteps(steps, k, size);
    initial_stones = [...b.black.map((p) => ['B', p]), ...b.white.map((p) => ['W', p])];
    moves = [];
  } else {
    initial_stones = head
      .filter((s) => s.kind === 'setup' && s.color && s.row != null && s.col != null)
      .map((s) => [s.color as string, canonToGtp(s.row as number, s.col as number, size)]);
    moves = head.filter(played).map((s) => [
      recordedColor(s) as string,
      s.kind === 'pass' || s.row == null || s.col == null ? 'pass' : canonToGtp(s.row, s.col, size),
    ]);
  }
  // 后端不收 initialPlayer:KataGo 按「最后一手的反色,没有手顺就黑」定走子方。对不上(让子谱轮白、AE 退化)
  // 就补一手对方 pass —— 盘面不变,走子方就对了。
  const mover = hintMover(steps, k);
  const implied: Color = moves.length ? other(moves[moves.length - 1][0] as Color) : 'B';
  if (implied !== mover) moves = [...moves, [implied, 'pass']];
  return {
    moves,
    initial_stones,
    board_size: size,
    komi: meta?.komi ?? 7.5,
    rules: meta?.ruleset || 'chinese',
    max_visits: 200,
  };
}

function toLed(move: string, size: number): LedPoint | null {
  const col = GTP_COLS.indexOf(move[0]);
  const n = Number(move.slice(1));
  if (col < 0 || !Number.isInteger(n) || n < 1 || n > size) return null; // pass / 不认识的
  return { row: size - n, col, color: 'hint' };
}

interface RawMove { move: string; winrate: number; scoreLead?: number }

export function useBaipuHint(o: {
  steps: BaipuStep[];
  k: number;
  boardSize: number;
  meta: BaipuMeta | null;
  sessionKey?: string;
}): BaipuHint {
  const { token } = useAuth();
  const { steps, k, boardSize, meta, sessionKey } = o;
  // Bind hints to this exact position/session. A source/account reload can keep
  // the same k, and returning to an earlier k must not reopen an old request.
  const position = useMemo(() => ({ steps, k, boardSize, token, sessionKey }), [steps, k, boardSize, token, sessionKey]);
  const [forPosition, setForPosition] = useState<typeof position | null>(null);
  const [status, setStatus] = useState<HintStatus>('idle');
  const [rows, setRows] = useState<HintRow[]>([]);
  const reqRef = useRef(0);
  const open = forPosition === position;

  useEffect(() => () => { reqRef.current += 1; }, [position]);

  const close = useCallback(() => {
    reqRef.current += 1; // 晚到的响应不回填
    setForPosition(null);
    setStatus('idle');
    setRows([]);
  }, []);

  const toggle = useCallback(() => {
    if (open) { close(); return; }
    const id = ++reqRef.current;
    const mover = hintMover(steps, k);
    setForPosition(position);
    setStatus('loading');
    setRows([]);
    API.quickAnalyze(buildHintRequest(steps, k, boardSize, meta), token ?? undefined)
      .then((result) => {
        if (reqRef.current !== id) return;
        const turn = result?.turnInfos?.[0] ?? result;
        const raw = ((turn?.moveInfos ?? []) as RawMove[]).slice(0, 3);
        setRows(raw.map((m) => ({
          move: m.move,
          winrate: mover === 'B' ? m.winrate : 1 - m.winrate,
          scoreLead: mover === 'B' ? (m.scoreLead ?? 0) : -(m.scoreLead ?? 0),
        })));
        setStatus('ok');
      })
      .catch(() => {
        if (reqRef.current !== id) return;
        setStatus('error'); // 算不出来就说算不出来,不留假数
      });
  }, [open, close, token, steps, k, boardSize, meta, position]);

  useEffect(() => {
    if (!open) return undefined;
    const h = setTimeout(close, HINT_TIMEOUT_MS);
    return () => clearTimeout(h);
  }, [open, close]);

  const leds = useMemo(
    () => (open ? rows.map((r) => toLed(r.move, boardSize)).filter((p): p is LedPoint => p !== null) : []),
    [open, rows, boardSize],
  );
  // Old position/session responses cannot expose rows or LEDs in the new scope.
  return open ? { open, status, rows, leds, toggle, close } : { open, status: 'idle', rows: NO_ROWS, leds, toggle, close };
}
