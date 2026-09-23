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
const played = (s: BaipuStep) => (s.kind === 'move' || s.kind === 'pass') && !!s.color;

/** 轮谁走:从第 k 步往后第一手的颜色;摆到最后就取最后一手的反色;一手都没有取黑。 */
export function hintMover(steps: readonly BaipuStep[], k: number): Color {
  const ahead = steps.slice(k).find(played);
  if (ahead) return ahead.color as Color;
  const behind = steps.slice(0, k).reverse().find(played);
  return behind ? other(behind.color as Color) : 'B';
}

export function buildHintRequest(steps: readonly BaipuStep[], k: number, size: number, meta: BaipuMeta | null) {
  const head = steps.slice(0, k);
  let moves: string[][];
  let initial_stones: string[][];
  if (head.some((s) => s.kind === 'clear')) {
    // AE(擦掉几颗)在 quick-analyze 里无从表达 —— 退化成把第 k 手的整盘当初始子、不带手顺。罕见。
    const b = replayBaipuSteps(steps, k, size);
    initial_stones = [...b.black.map((p) => ['B', p]), ...b.white.map((p) => ['W', p])];
    moves = [];
  } else {
    initial_stones = head
      .filter((s) => s.kind === 'setup' && s.color && s.row != null && s.col != null)
      .map((s) => [s.color as string, canonToGtp(s.row as number, s.col as number, size)]);
    moves = head.filter(played).map((s) => [
      s.color as string,
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

export function useBaipuHint(o: { steps: BaipuStep[]; k: number; boardSize: number; meta: BaipuMeta | null }): BaipuHint {
  const { token } = useAuth();
  const { steps, k, boardSize, meta } = o;
  // 记下「为第几手开的」,`open` 由它推出 —— 换了一手就自然收起,不用在 effect 里 setState
  // (仓里 `react-hooks/set-state-in-effect` 开着,`useAutoCount.ts:38` 同一个做法)。
  const [forK, setForK] = useState<number | null>(null);
  const [status, setStatus] = useState<HintStatus>('idle');
  const [rows, setRows] = useState<HintRow[]>([]);
  const reqRef = useRef(0);
  const open = forK === k;

  const close = useCallback(() => {
    reqRef.current += 1; // 晚到的响应不回填
    setForK(null);
    setStatus('idle');
    setRows([]);
  }, []);

  const toggle = useCallback(() => {
    if (open) { close(); return; }
    const id = ++reqRef.current;
    const mover = hintMover(steps, k);
    setForK(k);
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
  }, [open, close, token, steps, k, boardSize, meta]);

  useEffect(() => {
    if (!open) return undefined;
    const h = setTimeout(close, HINT_TIMEOUT_MS);
    return () => clearTimeout(h);
  }, [open, close]);

  const leds = useMemo(
    () => (open ? rows.map((r) => toLed(r.move, boardSize)).filter((p): p is LedPoint => p !== null) : []),
    [open, rows, boardSize],
  );
  // 换了一手之后 forK 对不上:旧那一手的行即使晚到落进了 state,也不往外给。
  return open ? { open, status, rows, leds, toggle, close } : { open, status: 'idle', rows: NO_ROWS, leds, toggle, close };
}
