import { act, renderHook } from '@testing-library/react';
import { expect, it } from 'vitest';
import { useResearchBoard } from './useResearchBoard';

it('reports only accepted placement or movement, keeping selection, deletion, same point, and no tool silent', () => {
  const { result } = renderHook(() => useResearchBoard());
  let accepted: unknown;
  act(() => { accepted = result.current.handleIntersectionClick(3, 3); });
  expect(accepted).toBe(true);
  act(() => result.current.setEditMode('move'));
  act(() => { accepted = result.current.handleIntersectionClick(3, 3); });
  expect(accepted).toBe(false);
  act(() => { accepted = result.current.handleIntersectionClick(3, 3); });
  expect(accepted).toBe(false);
  act(() => { result.current.handleIntersectionClick(3, 3); accepted = result.current.handleIntersectionClick(4, 4); });
  expect(accepted).toBe(true);
  act(() => result.current.setEditMode('delete'));
  act(() => { accepted = result.current.handleIntersectionClick(4, 4); });
  expect(accepted).toBe(false);
  act(() => { result.current.setEditMode(null); result.current.setPlaceMode(null); });
  act(() => { accepted = result.current.handleIntersectionClick(3, 3); });
  expect(accepted).toBe(false);
});
