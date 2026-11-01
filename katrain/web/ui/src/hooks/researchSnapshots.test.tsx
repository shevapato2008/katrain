import { act, renderHook } from '@testing-library/react';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { useResearchBoard as useGalaxyBoard } from '../galaxy/hooks/useResearchBoard';
import { useResearchBoard as useKioskBoard } from '../kiosk/hooks/useResearchBoard';

const source = '(;FF[4]SZ[19]KM[6.5]RU[japanese]AB[dp][pd]AW[dd]PL[W];W[pp];B[qq])';
function canonical(sgf: string) {
  return JSON.parse(execFileSync('python3', ['-c', 'import json,sys; from katrain.web.core.billing_input import canonical_analysis_input; print(json.dumps(canonical_analysis_input(json.load(sys.stdin), "position", "normal")))'], {
    cwd: resolve(process.cwd(), '../../..'), input: JSON.stringify(sgf), encoding: 'utf8',
  })) as { initial_player: string; initial_stones: string[][]; moves: string[][]; move_count: number; rules: string; komi: number; fingerprint: string };
}

for (const surface of ['galaxy', 'kiosk'] as const) {
  describe(`${surface} complete research snapshots`, () => {
    const useBoard = surface === 'galaxy' ? useGalaxyBoard : useKioskBoard;
    it('turns explicit same-color placement into a new setup and passes the real canonical validator', () => {
      const { result } = renderHook(() => useBoard());
      act(() => {
        if ('setBoardTool' in result.current) result.current.setBoardTool('black');
        else result.current.setPlaceMode('black');
      });
      act(() => { result.current.handleIntersectionClick(3, 3); });
      act(() => { result.current.handleIntersectionClick(15, 15); });
      const exported = result.current.serializeToSGF();
      expect(exported.sgf).toContain('AB[dp][pd]');
      expect(exported.sgf).not.toContain(';B[');
      expect(exported.sgf).toContain('PL[B]');
      expect(canonical(exported.sgf)).toMatchObject({ initial_stones: [['B', 'Q16'], ['B', 'D4']], initial_player: 'B', moves: [], move_count: 0 });
      expect(result.current.editedSetup).toBe(true);
    });
    it('preserves imported AB/AW/PL and all legal history through the selected cursor', () => {
      const { result } = renderHook(() => useBoard());
      act(() => { expect(result.current.loadFromSGF(source).success).toBe(true); });
      expect(result.current.handicapCount).toBe(3);
      act(() => { result.current.handleMoveChange(4); });
      const selected = result.current.serializeToSGF({ position: true });
      expect(selected.sgf).toContain('AB[dp][pd]');
      expect(selected.sgf).toContain('AW[dd]');
      expect(selected.sgf).toContain('PL[W]');
      expect(canonical(selected.sgf)).toMatchObject({ initial_player: 'W', initial_stones: [['B', 'Q16'], ['B', 'D4'], ['W', 'D16']], moves: [['W', 'Q4']], rules: 'japanese', komi: 6.5 });
      expect(canonical(result.current.serializeToSGF().sgf).moves).toEqual([['W', 'Q4'], ['B', 'R3']]);
      act(() => { result.current.handleMoveChange(0); });
      expect(result.current.currentMove).toBe(3);
      expect(result.current.nextColor).toBe('W');
      expect(canonical(result.current.serializeToSGF({ position: true }).sgf).moves).toEqual([]);
    });
    it('keeps capture history until an explicit edit starts a new setup from surviving stones', () => {
      const { result } = renderHook(() => useBoard());
      act(() => { result.current.loadFromSGF('(;SZ[19]KM[7.5]RU[chinese];B[ba];W[aa];B[ab])'); });
      expect(canonical(result.current.serializeToSGF({ position: true }).sgf).moves).toEqual([['B', 'B19'], ['W', 'A19'], ['B', 'A18']]);
      act(() => {
        if ('setBoardTool' in result.current) result.current.setBoardTool('black');
        else result.current.setPlaceMode('black');
      });
      act(() => { result.current.handleIntersectionClick(3, 3); });
      expect(canonical(result.current.serializeToSGF().sgf)).toMatchObject({ initial_stones: [['B', 'B19'], ['B', 'A18'], ['B', 'D4']], initial_player: 'W', moves: [] });
    });
    it('does not inherit setup, PL, handicap, rules, or komi from a previous import', () => {
      const { result } = renderHook(() => useBoard());
      act(() => { result.current.loadFromSGF('(;SZ[19]HA[2]KM[0.5]RU[japanese]AB[dd][pp]PL[W])'); });
      act(() => { result.current.loadFromSGF('(;SZ[19];B[pd])'); });
      expect(result.current.handicapCount).toBe(0);
      expect(result.current.handicap).toBe(0);
      expect(canonical(result.current.serializeToSGF().sgf)).toMatchObject({ initial_stones: [], initial_player: 'B', moves: [['B', 'Q16']], rules: 'chinese', komi: 7.5 });
    });
  });
}
