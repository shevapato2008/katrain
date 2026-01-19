export interface TimeSettings {
  mainTime: number; // minutes
  byoyomiLength: number; // seconds
  byoyomiPeriods: number; // count
  minimalTimeUsage: number; // seconds
  sound: boolean;
}

export interface TeachingSettings {
  // Teaching Settings
  showDots: boolean[]; // array of booleans for different move ranges
  saveFeedback: boolean[]; // array of booleans
  saveMarks: boolean[]; // array of booleans
  evalThresholds: number[]; // array of thresholds

  // Analysis Settings
  showAI: boolean;
  lockAI: boolean;
  topMovesShow: string; // e.g., 'top_move_delta_score'
  visits: {
    fast: number;
    low: number;
    max: number;
  };
}

export interface SessionSettings {
  time: TimeSettings;
  teaching: TeachingSettings;
}

export const DEFAULT_TIME_SETTINGS: TimeSettings = {
  mainTime: 60,
  byoyomiLength: 30,
  byoyomiPeriods: 5,
  minimalTimeUsage: 0,
  sound: true,
};

export const DEFAULT_TEACHING_SETTINGS: TeachingSettings = {
  showDots: [true, true, true, true, true, true],
  saveFeedback: [true, true, true, true, false, false],
  saveMarks: [true, true, true, true, true, true],
  evalThresholds: [12, 6, 3, 1.5, 0.5, 0],
  showAI: true,
  lockAI: false,
  topMovesShow: 'top_move_delta_score',
  visits: {
    fast: 25,
    low: 100,
    max: 500,
  },
};
