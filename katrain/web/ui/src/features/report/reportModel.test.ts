import { describe, expect, it } from 'vitest';

import type { ReportTaskMove, ReportTaskSummary } from '../../api/reportApi';
import type { KifuAlbumSummary } from '../../types/kifu';
import {
  buildReportStatesByGame,
  createOptimisticReportTask,
  isActiveReportTask,
  nextReportCursor,
  reconcileReportTasks,
  toLibraryUserGameParams,
  toLocalUserGameParams,
  toMoveAnalysisMap,
} from './reportModel';

const task = (overrides: Partial<ReportTaskSummary> = {}): ReportTaskSummary => ({
  id: 1,
  user_game_id: 'game-1',
  status: 'pending',
  report_type: 'normal',
  total_moves: 120,
  analyzed_moves: 0,
  requested_visits: 500,
  ...overrides,
});

const reportMove = (overrides: Partial<ReportTaskMove> = {}): ReportTaskMove => ({
  id: 1,
  task_id: 8,
  move_number: 1,
  status: 'completed',
  winrate: 0.52,
  score_lead: 1.4,
  visits: 500,
  top_moves: [],
  ownership: null,
  actual_move: 'Q16',
  actual_player: 'B',
  delta_score: 0,
  delta_winrate: 0,
  ...overrides,
});

describe('report task state', () => {
  it.each([
    ['pending', true],
    ['running', true],
    ['completed', false],
    ['failed', false],
    ['cancelling', false],
  ])('classifies %s tasks as active=%s', (status, expected) => {
    expect(isActiveReportTask(task({ status }))).toBe(expected);
  });

  it.each([
    ['normal', 500],
    ['deep', 2000],
  ] as const)('creates deterministic %s optimistic tasks', (reportType, requestedVisits) => {
    expect(createOptimisticReportTask('game-9', reportType, 0, -42)).toEqual({
      id: -42,
      user_game_id: 'game-9',
      status: 'pending',
      report_type: reportType,
      total_moves: 0,
      analyzed_moves: 0,
      requested_visits: requestedVisits,
    });
  });

  it('records the server task ids known when an optimistic mutation begins', () => {
    expect(createOptimisticReportTask('game-9', 'normal', 120, -43, [11, 14]))
      .toMatchObject({ baseline_server_task_ids: [11, 14] });
  });

  it('removes an optimistic task when a real task for the same game and type arrives', () => {
    const optimisticNormal = task({ id: -1 });
    const optimisticDeep = task({ id: -2, report_type: 'deep', requested_visits: 2000 });
    const realNormal = task({ id: 14, status: 'running' });

    expect(reconcileReportTasks([realNormal], [optimisticNormal, optimisticDeep])).toEqual([
      optimisticDeep,
      realNormal,
    ]);
  });

  it.each(['failed', 'completed'] as const)(
    'keeps a new optimistic task when only a historical %s task has the same game and type',
    (status) => {
      const optimistic = createOptimisticReportTask('game-1', 'normal', 120, -20, [14]);
      const historical = task({ id: 14, status });

      expect(reconcileReportTasks([historical], [optimistic])).toEqual([optimistic, historical]);
    },
  );

  it.each(['failed', 'completed'] as const)(
    'removes an optimistic task when a newly observed matching task is already %s',
    (status) => {
      const optimistic = createOptimisticReportTask('game-1', 'normal', 120, -20, [10]);
      const newlyObserved = task({ id: 14, status });

      expect(reconcileReportTasks([newlyObserved], [optimistic])).toEqual([newlyObserved]);
    },
  );

  it('keeps optimistic tasks for unrelated games and report types', () => {
    const optimistic = task({ id: -1, user_game_id: 'game-2' });
    const server = task({ id: 9, report_type: 'deep' });

    expect(reconcileReportTasks([server], [optimistic])).toEqual([optimistic, server]);
  });

  it('uses the newest task for each type and state while keeping normal and deep independent', () => {
    const tasks = [
      task({ id: 2, status: 'completed' }),
      task({ id: 8, status: 'completed' }),
      task({ id: 6, status: 'failed', report_type: 'deep' }),
      task({ id: 9, status: 'failed', report_type: 'deep' }),
      task({ id: 4, status: 'pending' }),
      task({ id: 7, status: 'running' }),
      task({ id: 5, status: 'running', report_type: 'deep' }),
    ];

    expect(buildReportStatesByGame(tasks)).toEqual({
      'game-1': {
        activeNormal: tasks[5],
        activeDeep: tasks[6],
        completedNormal: tasks[1],
        failedDeep: tasks[3],
      },
    });
  });

  it('uses the more-negative optimistic id as newer and ranks optimistic active tasks above server tasks', () => {
    const olderOptimistic = task({ id: -100 });
    const newerOptimistic = task({ id: -200 });
    const serverTask = task({ id: 99, status: 'running' });

    expect(buildReportStatesByGame([olderOptimistic, serverTask, newerOptimistic])).toEqual({
      'game-1': { activeNormal: newerOptimistic },
    });
  });
});

describe('user game import mapping', () => {
  it('maps a local SGF import to shared user-game parameters', () => {
    expect(toLocalUserGameParams({
      title: 'Local game',
      sgfContent: '(;GM[1])',
      boardSize: 19,
      rules: 'japanese',
      komi: 6.5,
      moveCount: 0,
      playerBlack: 'Black',
      playerWhite: 'White',
      blackRank: '1d',
      whiteRank: '2d',
    })).toEqual({
      sgf_content: '(;GM[1])',
      source: 'import',
      title: 'Local game',
      player_black: 'Black',
      player_white: 'White',
      black_rank: '1d',
      white_rank: '2d',
      board_size: 19,
      rules: 'japanese',
      komi: 6.5,
      move_count: 0,
      category: 'game',
    });
  });

  it('maps a library SGF and preserves valid zero values', () => {
    const album: KifuAlbumSummary = {
      id: 3,
      player_black: 'Black',
      player_white: 'White',
      black_rank: null,
      white_rank: null,
      event: null,
      result: null,
      rules: null,
      date_played: null,
      komi: 0,
      handicap: 0,
      board_size: 9,
      round_name: null,
      move_count: 0,
    };

    expect(toLibraryUserGameParams(album, '(;SZ[9])')).toEqual({
      sgf_content: '(;SZ[9])',
      source: 'kifu_library',
      title: 'Black vs White',
      player_black: 'Black',
      player_white: 'White',
      black_rank: undefined,
      white_rank: undefined,
      result: undefined,
      board_size: 9,
      rules: 'chinese',
      komi: 0,
      move_count: 0,
      category: 'game',
      event: undefined,
      round_name: undefined,
      game_date: undefined,
    });
  });
});

describe('report move analysis mapping', () => {
  it('maps complete analysis rows and preserves zero deltas', () => {
    expect(toMoveAnalysisMap([reportMove()], 'game-7')).toEqual({
      1: {
        match_id: 'game-7',
        move_number: 1,
        move: 'Q16',
        player: 'B',
        winrate: 0.52,
        score_lead: 1.4,
        top_moves: [],
        ownership: null,
        is_brilliant: false,
        is_mistake: false,
        is_questionable: false,
        delta_score: 0,
        delta_winrate: 0,
      },
    });
  });

  it.each([
    ['winrate', { winrate: null }],
    ['score lead', { score_lead: null }],
  ])('skips rows with null %s', (_label, overrides) => {
    expect(toMoveAnalysisMap([reportMove(overrides)], 'game-7')).toEqual({});
  });

  it('defaults nullable values and derives move classifications', () => {
    const brilliant = reportMove({ move_number: 2, top_moves: null, delta_score: 2, delta_winrate: null });
    const mistake = reportMove({ move_number: 3, delta_score: -3 });
    const questionable = reportMove({ move_number: 4, delta_score: -1.5 });

    const result = toMoveAnalysisMap([brilliant, mistake, questionable], 'game-7');

    expect(result[2]).toMatchObject({ top_moves: [], delta_winrate: 0, is_brilliant: true });
    expect(result[3]).toMatchObject({ is_mistake: true, is_questionable: true });
    expect(result[4]).toMatchObject({ is_mistake: false, is_questionable: true });
  });
});

describe('report cursor updates', () => {
  it.each([
    [12, 20, 24, 12],
    [20, 20, 24, 24],
    [30, 30, 12, 12],
    [30, 40, 12, 12],
    [4, 4, 0, 0],
  ])('maps cursor %i at frontier %i with next frontier %i to %i', (
    previousCursor,
    previousFrontier,
    nextFrontier,
    expected,
  ) => {
    expect(nextReportCursor(previousCursor, previousFrontier, nextFrontier)).toBe(expected);
  });
});
