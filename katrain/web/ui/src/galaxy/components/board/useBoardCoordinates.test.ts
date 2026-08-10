import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useBoardCoordinates } from './useBoardCoordinates';

describe('useBoardCoordinates', () => {
  it('automatically hides below 500px and shows from 500px', () => {
    expect(renderHook(() => useBoardCoordinates(499)).result.current.visible).toBe(false);
    expect(renderHook(() => useBoardCoordinates(500)).result.current.visible).toBe(true);
  });

  it('toggles the currently rendered visibility and keeps the override across resizing', () => {
    const { result, rerender } = renderHook(({ edge }) => useBoardCoordinates(edge), {
      initialProps: { edge: 499 },
    });

    act(() => result.current.toggle());
    expect(result.current.visible).toBe(true);
    expect(result.current.userOverride).toBe(true);

    rerender({ edge: 700 });
    expect(result.current.visible).toBe(true);
    expect(result.current.userOverride).toBe(true);

    act(() => result.current.toggle());
    expect(result.current.visible).toBe(false);
    expect(result.current.userOverride).toBe(false);

    rerender({ edge: 320 });
    expect(result.current.visible).toBe(false);
    expect(result.current.userOverride).toBe(false);
  });

  it('can reset to automatic mode and a new mount starts automatic', () => {
    const first = renderHook(({ edge }) => useBoardCoordinates(edge), { initialProps: { edge: 499 } });
    act(() => first.result.current.toggle());
    expect(first.result.current.userOverride).toBe(true);

    act(() => first.result.current.resetToAutomatic());
    expect(first.result.current.userOverride).toBeNull();
    expect(first.result.current.visible).toBe(false);
    first.unmount();

    const second = renderHook(() => useBoardCoordinates(499));
    expect(second.result.current.userOverride).toBeNull();
    expect(second.result.current.visible).toBe(false);
  });
});
