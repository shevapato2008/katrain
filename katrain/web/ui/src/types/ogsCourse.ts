/** Public, localized OGS course reads. Coordinates are zero-based on the full board. */
export type OgsPoint = [number, number];
export type OgsPlayer = 'B' | 'W';

export interface OgsCourseChapter {
  id: string;
  number: number;
  title: string;
  lesson_count: number;
  step_count: number;
}

export interface OgsCourseLesson {
  id: string;
  chapter_id: string;
  order: number;
  course_code: string;
  route: string;
  title: string;
  subtext: string;
  step_count: number;
  first_page: number;
}

export interface OgsCourseIndex {
  book_id: number;
  title: string;
  source: {
    repository: string;
    commit: string;
    locale_version: string;
    license: string;
  };
  languages: string[];
  chapters: OgsCourseChapter[];
  lessons: OgsCourseLesson[];
  counts: {
    chapters: number;
    lessons: number;
    steps: number;
    languages: number;
    screenshots: number;
    exercise_kinds: Record<string, number>;
    unsupported: number;
  };
  license_notice: string;
}

export interface OgsAnswerNode {
  point: OgsPoint | null;
  correct: boolean;
  wrong: boolean;
  children: OgsAnswerNode[];
}

export type OgsExercise =
  | { kind: 'puzzle'; tree: OgsAnswerNode }
  | { kind: 'choice'; choices: Array<{ value: string; label_key: string }>; correct_choice: string }
  | { kind: 'pass' }
  | { kind: 'remove'; remove_targets: OgsPoint[] }
  | { kind: 'finish' };

export interface OgsStep {
  book_id: number;
  figure_id: number;
  source_id: string;
  source_url: string;
  lesson_id: string;
  step: number;
  page: number;
  size: number;
  initial_player: OgsPlayer;
  stones: Record<OgsPlayer, OgsPoint[]>;
  viewport: { col: number; row: number; cols: number; rows: number } | null;
  letters: Record<string, string>;
  shapes: Record<string, string>;
  exercise: OgsExercise;
  locale: {
    requested: string;
    effective: string;
    text: { title: string; instruction: string; choices?: Record<string, string>; fallback?: boolean };
  };
  screenshot: { image_path: string; language: string; width: number; height: number } | null;
  screenshot_status: 'ready' | 'pending';
}
