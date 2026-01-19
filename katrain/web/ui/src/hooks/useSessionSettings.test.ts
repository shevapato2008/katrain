import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useSessionSettings } from './useSessionSettings';
import { DEFAULT_TIME_SETTINGS, DEFAULT_TEACHING_SETTINGS } from '../types/settings';

describe('useSessionSettings', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('should initialize with default settings when sessionStorage is empty', () => {
    const { result } = renderHook(() => useSessionSettings());
    expect(result.current.timeSettings).toEqual(DEFAULT_TIME_SETTINGS);
    expect(result.current.teachingSettings).toEqual(DEFAULT_TEACHING_SETTINGS);
  });

  it('should load settings from sessionStorage if they exist', () => {
    const storedTime = { ...DEFAULT_TIME_SETTINGS, mainTime: 120 };
    sessionStorage.setItem('katrain_time_settings', JSON.stringify(storedTime));

    const { result } = renderHook(() => useSessionSettings());
    expect(result.current.timeSettings).toEqual(storedTime);
  });

  it('should update time settings and persist to sessionStorage', () => {
    const { result } = renderHook(() => useSessionSettings());
    
    act(() => {
      result.current.updateTimeSettings({ mainTime: 90 });
    });

    expect(result.current.timeSettings.mainTime).toBe(90);
    expect(JSON.parse(sessionStorage.getItem('katrain_time_settings')!)).toMatchObject({ mainTime: 90 });
  });

  it('should update teaching settings and persist to sessionStorage', () => {
    const { result } = renderHook(() => useSessionSettings());
    
    act(() => {
      result.current.updateTeachingSettings({ showAI: false });
    });

    expect(result.current.teachingSettings.showAI).toBe(false);
    expect(JSON.parse(sessionStorage.getItem('katrain_teaching_settings')!)).toMatchObject({ showAI: false });
  });
});
