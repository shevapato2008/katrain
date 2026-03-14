export interface TutorialCategory {
  id: string;
  slug: string;
  title: string;
  summary: string;
  order: number;
  topic_count: number;
  cover_asset: string | null;
}

export interface TutorialTopic {
  id: string;
  category_id: string;
  slug: string;
  title: string;
  summary: string;
  tags: string[] | null;
  difficulty: string | null;
  estimated_minutes: number | null;
}

export type BoardMode = 'image' | 'sgf';

export interface TutorialStep {
  id: string;
  example_id: string;
  order: number;
  narration: string;
  image_asset: string | null;
  audio_asset: string | null;
  audio_duration_ms: number | null;
  board_mode: BoardMode;
  board_payload: unknown | null;
}

export interface TutorialExample {
  id: string;
  topic_id: string;
  title: string;
  summary: string;
  order: number;
  total_duration_sec: number | null;
  step_count: number;
  steps: TutorialStep[];
}

export interface TutorialProgress {
  example_id: string;
  topic_id: string;
  last_step_id: string | null;
  completed: boolean;
  last_played_at: string | null;
}

export interface ProgressUpdate {
  topic_id: string;
  last_step_id: string;
  completed: boolean;
}
