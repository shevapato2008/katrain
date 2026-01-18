import { useState, useEffect } from 'react';
import { TimeSettings, TeachingSettings, DEFAULT_TIME_SETTINGS, DEFAULT_TEACHING_SETTINGS } from '../types/settings';

const TIME_SETTINGS_KEY = 'katrain_time_settings';
const TEACHING_SETTINGS_KEY = 'katrain_teaching_settings';

export const useSessionSettings = () => {
  const [timeSettings, setTimeSettings] = useState<TimeSettings>(() => {
    try {
      const stored = sessionStorage.getItem(TIME_SETTINGS_KEY);
      return stored ? JSON.parse(stored) : DEFAULT_TIME_SETTINGS;
    } catch {
      return DEFAULT_TIME_SETTINGS;
    }
  });

  const [teachingSettings, setTeachingSettings] = useState<TeachingSettings>(() => {
    try {
      const stored = sessionStorage.getItem(TEACHING_SETTINGS_KEY);
      return stored ? JSON.parse(stored) : DEFAULT_TEACHING_SETTINGS;
    } catch {
      return DEFAULT_TEACHING_SETTINGS;
    }
  });

  const updateTimeSettings = (updates: Partial<TimeSettings>) => {
    setTimeSettings((prev) => {
      const newSettings = { ...prev, ...updates };
      sessionStorage.setItem(TIME_SETTINGS_KEY, JSON.stringify(newSettings));
      return newSettings;
    });
  };

  const updateTeachingSettings = (updates: Partial<TeachingSettings>) => {
    setTeachingSettings((prev) => {
      const newSettings = { ...prev, ...updates };
      sessionStorage.setItem(TEACHING_SETTINGS_KEY, JSON.stringify(newSettings));
      return newSettings;
    });
  };

  return {
    timeSettings,
    teachingSettings,
    updateTimeSettings,
    updateTeachingSettings,
  };
};
