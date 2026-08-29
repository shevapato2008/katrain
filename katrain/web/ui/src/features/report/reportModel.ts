import {
  isActiveReportStatus,
  type ReportTaskMove,
  type ReportTaskSummary,
  type ReportType,
} from '../../api/reportApi';
import type { CreateUserGameParams } from '../../api/userGamesApi';
import type { KifuAlbumSummary } from '../../types/kifu';
import type { MoveAnalysis } from '../../types/live';

export interface LocalReportImportPayload {
  title?: string;
  sgfContent: string;
  boardSize: number;
  rules: string;
  komi: number;
  moveCount: number;
  playerBlack?: string;
  playerWhite?: string;
  blackRank?: string;
  whiteRank?: string;
}

export interface ReportGameStatus {
  activeNormal?: ReportTaskSummary;
  activeDeep?: ReportTaskSummary;
  completedNormal?: ReportTaskSummary;
  completedDeep?: ReportTaskSummary;
  failedNormal?: ReportTaskSummary;
  failedDeep?: ReportTaskSummary;
}

export type ReportStatesByGame = Record<string, ReportGameStatus>;

export interface OptimisticReportTask extends ReportTaskSummary {
  baseline_server_task_ids?: readonly number[];
}

export function isActiveReportTask(task: ReportTaskSummary): boolean {
  return isActiveReportStatus(task.status);
}

export function createOptimisticReportTask(
  gameId: string,
  reportType: ReportType,
  moveCount: number,
  optimisticId: number,
  baselineServerTaskIds?: readonly number[],
): OptimisticReportTask {
  const task: OptimisticReportTask = {
    id: optimisticId,
    user_game_id: gameId,
    status: 'pending',
    report_type: reportType,
    total_moves: moveCount,
    analyzed_moves: 0,
    requested_visits: reportType === 'deep' ? 2000 : 500,
  };
  if (baselineServerTaskIds !== undefined) {
    task.baseline_server_task_ids = [...baselineServerTaskIds];
  }
  return task;
}

export function reconcileReportTasks(
  serverTasks: ReportTaskSummary[],
  optimisticTasks: OptimisticReportTask[],
): ReportTaskSummary[] {
  const consumedServerTaskIds = new Set<number>();
  const consumedOptimisticTaskIds = new Set<number>();

  // Match mutations FIFO. A server row can acknowledge only one optimistic request,
  // while the original optimistic ordering remains intact in the returned list.
  const oldestOptimisticFirst = [...optimisticTasks].sort((left, right) => right.id - left.id);
  for (const optimisticTask of oldestOptimisticFirst) {
    const baselineIds = optimisticTask.baseline_server_task_ids === undefined
      ? null
      : new Set(optimisticTask.baseline_server_task_ids);
    const counterpart = [...serverTasks]
      .sort((left, right) => left.id - right.id)
      .find((serverTask) => (
        !consumedServerTaskIds.has(serverTask.id)
        && serverTask.user_game_id === optimisticTask.user_game_id
        && serverTask.report_type === optimisticTask.report_type
        && (baselineIds ? !baselineIds.has(serverTask.id) : isActiveReportTask(serverTask))
      ));
    if (counterpart) {
      consumedServerTaskIds.add(counterpart.id);
      consumedOptimisticTaskIds.add(optimisticTask.id);
    }
  }

  const remainingOptimisticTasks = optimisticTasks.filter(
    (optimisticTask) => !consumedOptimisticTaskIds.has(optimisticTask.id),
  );
  return [...remainingOptimisticTasks, ...serverTasks];
}

export function buildReportStatesByGame(tasks: ReportTaskSummary[]): ReportStatesByGame {
  const states: ReportStatesByGame = {};
  const newestFirst = [...tasks].sort((left, right) => {
    const leftIsOptimistic = left.id < 0;
    const rightIsOptimistic = right.id < 0;

    // Optimistic IDs are negative and decrease as tasks are inserted; server IDs increase.
    if (leftIsOptimistic && rightIsOptimistic) return left.id - right.id;
    if (leftIsOptimistic) return -1;
    if (rightIsOptimistic) return 1;
    return right.id - left.id;
  });

  for (const task of newestFirst) {
    const state = states[task.user_game_id] ?? {};
    const isDeep = task.report_type === 'deep';

    if (task.status === 'completed') {
      if (isDeep) state.completedDeep ??= task;
      else state.completedNormal ??= task;
    } else if (task.status === 'failed') {
      if (isDeep) state.failedDeep ??= task;
      else state.failedNormal ??= task;
    } else if (isActiveReportTask(task)) {
      if (isDeep) state.activeDeep ??= task;
      else state.activeNormal ??= task;
    }

    states[task.user_game_id] = state;
  }

  return states;
}

export function toLocalUserGameParams(payload: LocalReportImportPayload): CreateUserGameParams {
  return {
    sgf_content: payload.sgfContent,
    source: 'import',
    title: payload.title,
    player_black: payload.playerBlack,
    player_white: payload.playerWhite,
    black_rank: payload.blackRank,
    white_rank: payload.whiteRank,
    board_size: payload.boardSize,
    rules: payload.rules,
    komi: payload.komi,
    move_count: payload.moveCount,
    category: 'game',
  };
}

export function toLibraryUserGameParams(
  album: KifuAlbumSummary,
  sgfContent: string,
): CreateUserGameParams {
  return {
    sgf_content: sgfContent,
    source: 'kifu_library',
    title: album.event || `${album.player_black} vs ${album.player_white}`,
    player_black: album.player_black,
    player_white: album.player_white,
    black_rank: album.black_rank || undefined,
    white_rank: album.white_rank || undefined,
    result: album.result || undefined,
    board_size: album.board_size,
    rules: album.rules || 'chinese',
    komi: album.komi ?? 7.5,
    move_count: album.move_count,
    category: 'game',
    event: album.event || undefined,
    round_name: album.round_name || undefined,
    game_date: album.date_played || undefined,
  };
}

export function toMoveAnalysisMap(
  reportMoves: ReportTaskMove[],
  userGameId: string,
): Record<number, MoveAnalysis> {
  const analysisByMove: Record<number, MoveAnalysis> = {};

  for (const move of reportMoves) {
    if (move.winrate == null || move.score_lead == null) continue;
    const deltaScore = move.delta_score ?? 0;
    analysisByMove[move.move_number] = {
      match_id: userGameId,
      move_number: move.move_number,
      move: move.actual_move,
      player: move.actual_player,
      winrate: move.winrate,
      score_lead: move.score_lead,
      top_moves: move.top_moves ?? [],
      ownership: move.ownership,
      // 这三个布尔量只为不破坏旧消费者而保留。判级已经移到服务端
      // （阈值真源 katrain/core/move_grade.yaml），新代码请读 grade。
      // 注意 is_brilliant 建在 delta_score 这根单边轴上，实测它基本只在
      // 搜索噪声上触发 —— 别再往它上面加功能。
      is_brilliant: deltaScore >= 2,
      is_mistake: deltaScore <= -3,
      is_questionable: deltaScore <= -1.5,
      delta_score: deltaScore,
      delta_winrate: move.delta_winrate ?? 0,
      grade: move.grade ?? null,
      points_lost: move.points_lost ?? null,
      is_top_move: move.is_top_move ?? null,
      top_prior: move.top_prior ?? null,
      brilliance: move.brilliance ?? null,
    };
  }

  return analysisByMove;
}

export function nextReportCursor(
  previousCursor: number,
  previousFrontier: number,
  nextFrontier: number,
): number {
  if (previousCursor === previousFrontier) return nextFrontier;
  return Math.min(previousCursor, nextFrontier);
}
