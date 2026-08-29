// AUTO-GENERATED from katrain/core/move_grade.yaml -- DO NOT EDIT BY HAND.
// Regenerate:  python -m katrain.core.move_grade --emit-ts
// A test (tests/test_move_grade.py::test_generated_ts_is_in_sync) fails if this
// file drifts from the yaml.

export type GradeId =
  | "brilliant"
  | "best"
  | "very_good"
  | "playable"
  | "inaccuracy"
  | "mistake"
  | "blunder"
  | "unrated";

export interface GradeTier {
  id: GradeId;
  i18nKey: string;
  zh: string;
  color: string;
  bad: boolean;
}

export const GRADE_TIERS: readonly GradeTier[] = [
  { id: "brilliant", i18nKey: "grade:brilliant", zh: "妙手", color: "#3FA2E8", bad: false },
  { id: "best", i18nKey: "grade:best", zh: "最佳", color: "#2E8B57", bad: false },
  { id: "very_good", i18nKey: "grade:very_good", zh: "很好", color: "#4DBE46", bad: false },
  { id: "playable", i18nKey: "grade:playable", zh: "可下", color: "#A4B436", bad: false },
  { id: "inaccuracy", i18nKey: "grade:inaccuracy", zh: "欠佳", color: "#D6A318", bad: true },
  { id: "mistake", i18nKey: "grade:mistake", zh: "失误", color: "#CF6B09", bad: true },
  { id: "blunder", i18nKey: "grade:blunder", zh: "恶手", color: "#BB2121", bad: true },
] as const;

export const GRADE_BY_ID: Readonly<Record<string, GradeTier>> = Object.fromEntries(
  GRADE_TIERS.map((t) => [t.id, t]),
);

export const BAD_GRADES: readonly GradeId[] = GRADE_TIERS.filter((t) => t.bad).map((t) => t.id);

export const GRADE_LADDER_POINTS = {
  very_good: 0.5,
  playable: 1.5,
  inaccuracy: 3.0,
  mistake: 6.0,
} as const;

export const PER_SIDE_LIMIT = 5;

export const SHOW_TRUNCATED_TOTAL = true;

export interface GradePhase {
  id: string;
  from: number;
  to: number | null;
}

export const GRADE_PHASES: readonly GradePhase[] = [
  { id: "opening", from: 0, to: 59 },
  { id: "midgame", from: 60, to: 149 },
  { id: "endgame", from: 150, to: null },
] as const;
