/** Presentation-only seam shared with Gomoku; no settings or catalog imports. */
export type GeometryTranslator = (key: string, fallback?: string) => string;
export const geometrySourceText: GeometryTranslator = (key, fallback) => fallback ?? key;
