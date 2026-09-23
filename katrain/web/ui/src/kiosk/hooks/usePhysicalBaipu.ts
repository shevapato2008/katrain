// 摆谱(屏 17)实体盘识别的 IO 层:消费 /ws/vision 事件、执行 physicalBaipuMachine 的命令(识别 REST / 灯)、
// 按页面的 k / 盘面变化决定下一步是「等下一手」还是「把盘面摆对」。所有判定逻辑在纯 reducer 里,这里保持薄。
//
// 与 usePhysicalTsumego 的一处刻意差异:**命令串行执行,每条 await 完再发下一条**。
// 死活题是 fire-and-forget,靠「确认要 3–5 帧」的时间差容忍乱序;摆谱不能靠它 —— 识别层约束 5:
// 解除暂停不重建基线,若 `pause(false)` 抢在 `setupMode` 之前落地,试下时摆的 1–3 颗子会被当成落子。
//
// 识别状态是全局单例、无归属(`vision.py:310-311`),所以卸载必须清场:撤臂、解除暂停、关监视、灭灯。

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../../api';
import { LedAPI } from '../../api/ledApi';
import type { VisionSyncEvent } from './useVisionSync';
import {
  initialState,
  reduce,
  type BaipuMachineState,
  type BaipuPhase,
  type Board,
  type Command,
  type LedPoint,
  type MachineEvent,
  type NextStone,
  type SetupReason,
} from './physicalBaipuMachine';

export type { BaipuPhase, NextStone, SetupReason, LedPoint } from './physicalBaipuMachine';

const BLINK_MS = 450;     // 同死活题:蓝灯(该拿走)与白灯(AI 候选)闪,常亮的灯被子一盖就看不见
const STUCK_MS = 10_000;  // setup 这么久没对上 ⇒ 露出「摆好了，继续」

export interface PhysicalBaipuOptions {
  /** 摄像头可用 && 非采集机 && 页面在摆(guiding) && 没有「接着摆?」对话框。 */
  enabled: boolean;
  /** /ws/vision 已连上。连上之前不发任何命令(空盘的 setup_complete 几乎立刻到,早发就丢了)。 */
  visionConnected: boolean;
  syncEvents: VisionSyncEvent[];
  /** 已摆手数。 */
  k: number;
  /** `replayBaipuMatrix(steps, k, 19)`。 */
  board: Board;
  /** 第 k 步可摆时它的落点;pass / AE / 摆完为 null。 */
  next: NextStone | null;
  /** 试下 || AI 支招开着。 */
  paused: boolean;
  /** 支招候选点(白闪);没开时 []。 */
  hintLeds: LedPoint[];
  /** 摄像头认到了正确的下一手 → 页面推进 k。 */
  onMatched: () => void;
}

export interface PhysicalBaipuState {
  phase: BaipuPhase;
  reason: SetupReason | null;
  missing: Array<[number, number]>;
  extra: Array<[number, number, number]>;
  wrong: [number, number] | null;
  /** setup 连续 10 s 没对上。 */
  stuck: boolean;
  ledOk: boolean;
  /** 页控条「重新点灯」:同一组点也重发一遍。 */
  relight: () => void;
  /** 「摆好了，继续」:按摄像头现在看到的盘面重新 setup(当帧即对上),对上后按它当期望盘面接着等下一手。 */
  adopt: () => void;
}

const sameBoard = (a: Board, b: Board) => a.every((row, r) => row.every((v, c) => v === b[r]?.[c]));
/** 旧盘面上有子、新盘面上没了(提子 / AE / 撤回)。 */
const hasRemoval = (prev: Board, cur: Board) => prev.some((row, r) => row.some((v, c) => v !== 0 && cur[r]?.[c] !== v));
/** 新盘面 = 旧盘面 + 至多一颗(没拿走、没变色)。 */
const addsAtMostOne = (prev: Board, cur: Board) => {
  if (hasRemoval(prev, cur)) return false;
  let added = 0;
  cur.forEach((row, r) => row.forEach((v, c) => { if (v !== 0 && prev[r]?.[c] === 0) added += 1; }));
  return added <= 1;
};

export function usePhysicalBaipu(opts: PhysicalBaipuOptions): PhysicalBaipuState {
  const { enabled, visionConnected, syncEvents, k, board, paused, hintLeds } = opts;

  const machineRef = useRef<BaipuMachineState>(initialState);
  const [ui, setUi] = useState<BaipuMachineState>(initialState);
  const [ledOk, setLedOk] = useState(true);
  const [stuck, setStuck] = useState(false);

  const optsRef = useRef(opts);
  optsRef.current = opts;
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const activeRef = useRef(false);                 // 生命周期开着(enabled && visionConnected)
  const genRef = useRef(0);                        // 生命周期代号:上一代排队没跑完的命令一律作废
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const processedSeqRef = useRef(-1);
  const matchedRef = useRef<{ promoted: boolean } | null>(null);
  const prevRef = useRef<{ k: number; board: Board } | null>(null);
  const prevPausedRef = useRef(paused);
  const relightTimerRef = useRef<number | undefined>(undefined);

  // ── 灯:常亮 ∪(闪烁相位为「亮」时的)闪烁点。同一组点不重发。 ──
  const steadyRef = useRef<LedPoint[]>([]);
  const blinkRef = useRef<LedPoint[]>([]);
  const blinkKeyRef = useRef('');
  const blinkOnRef = useRef(true);
  const lastLedKeyRef = useRef('');

  const renderLeds = useCallback(() => {
    const pts = blinkOnRef.current ? [...steadyRef.current, ...blinkRef.current] : steadyRef.current;
    const key = JSON.stringify(pts);
    if (key === lastLedKeyRef.current) return;
    lastLedKeyRef.current = key;
    (pts.length ? LedAPI.points(pts) : LedAPI.clear())
      .then((r) => setLedOk(r.connected))
      .catch(() => setLedOk(false));
  }, []);

  const setLeds = useCallback((steady: LedPoint[], blink: LedPoint[]) => {
    steadyRef.current = steady;
    const key = JSON.stringify(blink);
    if (key !== blinkKeyRef.current) {
      blinkKeyRef.current = key;
      blinkRef.current = blink;
      blinkOnRef.current = true; // 新的一组闪烁点先亮出来,再交给定时器翻转
    }
    renderLeds();
  }, [renderLeds]);

  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => {
      if (blinkRef.current.length === 0) return;
      blinkOnRef.current = !blinkOnRef.current;
      renderLeds();
    }, BLINK_MS);
    return () => window.clearInterval(id);
  }, [enabled, renderLeds]);

  // ── 命令:串行队列 ──
  const dispatchRef = useRef<(e: MachineEvent) => void>(() => {});

  const run = useCallback(async (cmd: Command) => {
    switch (cmd.kind) {
      case 'setupMode': await API.visionSetupMode(cmd.board); break;
      case 'expectedBoard': await API.visionExpectedBoard(cmd.board); break;
      case 'armMoves': await API.visionMoveDetection(cmd.armed); break;
      case 'pause': await API.visionPause(cmd.paused); break;
      case 'leds': setLeds(cmd.steady, cmd.blink); break;
      case 'relightLater':
        window.clearTimeout(relightTimerRef.current);
        relightTimerRef.current = window.setTimeout(() => dispatchRef.current({ type: 'RELIGHT' }), cmd.ms);
        break;
      case 'matched':
        matchedRef.current = { promoted: cmd.promoted };
        optsRef.current.onMatched();
        break;
    }
  }, [setLeds]);

  const enqueue = useCallback((commands: Command[]) => {
    if (commands.length === 0) return;
    const gen = genRef.current;
    queueRef.current = queueRef.current.then(async () => {
      for (const cmd of commands) {
        if (gen !== genRef.current) return; // 这一代已经结束
        try { await run(cmd); } catch { /* 单条失败不拦后面的;灯的失败由 ledOk 报 */ }
      }
    });
  }, [run]);

  const dispatch = useCallback((e: MachineEvent) => {
    const { state, commands } = reduce(machineRef.current, e);
    machineRef.current = state;
    setUi(state);
    if (e.type === 'SETUP' || e.type === 'AWAIT' || e.type === 'RESUME' || e.type === 'STOP') {
      window.clearTimeout(relightTimerRef.current);
    }
    enqueue(commands);
  }, [enqueue]);
  dispatchRef.current = dispatch;

  // ── 生命周期(必须写在事件消费前面:同一轮渲染里先把已到的旧事件标成处理过) ──
  useEffect(() => {
    if (!enabled || !visionConnected) return;
    genRef.current += 1;
    activeRef.current = true;
    const evs = optsRef.current.syncEvents;
    processedSeqRef.current = evs.length ? evs[evs.length - 1].seq : processedSeqRef.current;
    matchedRef.current = null;
    const o = optsRef.current;
    prevRef.current = { k: o.k, board: o.board };
    prevPausedRef.current = o.paused;
    queueRef.current = queueRef.current.then(() => API.visionMonitor(true)).catch(() => {});
    dispatch({ type: 'SETUP', board: o.board, next: o.next, reason: 'entry' });
    if (o.paused) dispatch({ type: 'PAUSE', leds: o.hintLeds });
    return () => {
      activeRef.current = false;
      genRef.current += 1;
      window.clearTimeout(relightTimerRef.current);
      machineRef.current = initialState;
      setUi(initialState);
      setStuck(false);
      queueRef.current = queueRef.current.then(async () => {
        await API.visionMoveDetection(false).catch(() => {});
        await API.visionPause(false).catch(() => {});
        await API.visionMonitor(false).catch(() => {});
      });
      steadyRef.current = [];
      blinkRef.current = [];
      blinkKeyRef.current = '';
      lastLedKeyRef.current = '';
      LedAPI.clear().catch(() => {});
    };
    // 只跟生命周期两个开关走;其余值从 optsRef 读当下的
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, visionConnected]);

  // ── /ws/vision 事件(seq 去重,每条恰好一次、按顺序) ──
  useEffect(() => {
    if (!enabled) return;
    for (const evt of syncEvents) {
      if (evt.seq <= processedSeqRef.current) continue;
      processedSeqRef.current = evt.seq;
      if (!activeRef.current || pausedRef.current) continue; // 暂停时识别层本来就不喂;这里再挡一道
      const d = evt.data as { missing?: Array<[number, number]>; extra?: Array<[number, number, number]>; row?: number; col?: number; color?: number };
      switch (evt.type) {
        case 'setup_progress': dispatch({ type: 'SETUP_PROGRESS', missing: d.missing ?? [], extra: d.extra ?? [] }); break;
        case 'setup_complete': dispatch({ type: 'SETUP_COMPLETE' }); break;
        case 'move_confirmed':
          if (d.row != null && d.col != null && d.color != null) dispatch({ type: 'MOVE_CONFIRMED', row: d.row, col: d.col, color: d.color });
          break;
        case 'move_pending':
          if (d.row != null && d.col != null) dispatch({ type: 'MOVE_PENDING', row: d.row, col: d.col });
          break;
        // illegal_change / ambiguous_stone / move_detected …:监视模式下是噪声(识别层约束 7)
        default: break;
      }
    }
  }, [enabled, syncEvents, dispatch]);

  // ── 页面的 k / 盘面变了:决定是直接等下一手,还是先把盘面摆对 ──
  const boardKey = useMemo(() => JSON.stringify(board), [board]);
  useEffect(() => {
    if (!activeRef.current) return;
    const prev = prevRef.current;
    const o = optsRef.current;
    if (!prev || (prev.k === o.k && sameBoard(prev.board, o.board))) return;
    prevRef.current = { k: o.k, board: o.board };
    if (pausedRef.current) return; // 恢复时会拿当下盘面 setup
    const matched = matchedRef.current;
    matchedRef.current = null;
    const removed = hasRemoval(prev.board, o.board);
    if (matched) {
      if (matched.promoted) {
        // 提升是在 setup 里认到的 —— 识别层还在 setup_in_progress,不重新 setup 就收不到落子
        dispatch({ type: 'SETUP', board: o.board, next: o.next, reason: removed ? 'capture' : 'verify' });
      } else if (addsAtMostOne(prev.board, o.board)) {
        dispatch({ type: 'AWAIT', board: o.board, next: o.next });
      } else {
        dispatch({ type: 'SETUP', board: o.board, next: o.next, reason: 'capture' });
      }
      return;
    }
    const m = machineRef.current;
    if (o.k > prev.k && sameBoard(prev.board, o.board)) {
      // 页面自己跳过了虚手(pass)。还在把盘面摆对的话留在 setup,只换下一手 —— 被提的子可能还没拿走
      if (m.phase === 'setup') dispatch({ type: 'SETUP', board: o.board, next: o.next, reason: m.reason ?? 'entry' });
      else dispatch({ type: 'AWAIT', board: o.board, next: o.next });
    } else if (o.k < prev.k) {
      dispatch({ type: 'SETUP', board: o.board, next: o.next, reason: 'undo' });
    } else {
      dispatch({ type: 'SETUP', board: o.board, next: o.next, reason: 'capture' });
    }
  }, [boardKey, k, dispatch]);

  // ── 试下 / 支招:暂停与恢复 ──
  useEffect(() => {
    if (!activeRef.current) { prevPausedRef.current = paused; return; }
    const o = optsRef.current;
    if (paused && !prevPausedRef.current) dispatch({ type: 'PAUSE', leds: o.hintLeds });
    else if (!paused && prevPausedRef.current) dispatch({ type: 'RESUME', board: o.board, next: o.next });
    prevPausedRef.current = paused;
  }, [paused, dispatch]);

  // 暂停中支招候选变了(算完了 / 收起了):只换灯
  const hintKey = JSON.stringify(hintLeds);
  useEffect(() => {
    if (!activeRef.current || !pausedRef.current) return;
    const leds = optsRef.current.hintLeds;
    const gen = genRef.current;
    queueRef.current = queueRef.current.then(() => { if (gen === genRef.current) setLeds([], leds); });
  }, [hintKey, setLeds]);

  // ── setup 卡住计时 ──
  useEffect(() => {
    setStuck(false);
    if (ui.phase !== 'setup') return;
    const id = window.setTimeout(() => setStuck(true), STUCK_MS);
    return () => window.clearTimeout(id);
  }, [ui.phase, ui.reason, ui.target]);

  const relight = useCallback(() => {
    lastLedKeyRef.current = ''; // 同一组点也重发:灯板重连后要的就是这一下
    dispatch({ type: 'RELIGHT' });
  }, [dispatch]);

  const adopt = useCallback(() => {
    if (!activeRef.current) return;
    API.visionDetectedBoard()
      .then((r) => {
        if (!activeRef.current || !Array.isArray(r?.board)) return;
        dispatch({ type: 'SETUP', board: r.board, next: optsRef.current.next, reason: 'adopt' });
      })
      .catch(() => {});
  }, [dispatch]);

  return {
    phase: ui.phase,
    reason: ui.reason,
    missing: ui.missing,
    extra: ui.extra,
    wrong: ui.wrong,
    stuck,
    ledOk,
    relight,
    adopt,
  };
}
