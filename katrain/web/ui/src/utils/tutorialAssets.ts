import type { TutorialFigure } from '../types/tutorial';
import { TutorialReadAPI } from '../api/tutorialApi';

const SLUG_RE = /tutorial_assets\/([^/]+)\//;

/**
 * Resolve the book slug from a section's figures by parsing the
 * `tutorial_assets/{slug}/...` prefix of the first figure that carries any
 * asset path (page image, video, or audio). Returns null when no slug can be
 * parsed (e.g. figures empty or none have asset paths).
 *
 * This is the deep-link-safe way to build section video URLs without a backend
 * change: the section detail endpoint does not expose the book slug.
 */
export function bookSlugFromFigures(figures: TutorialFigure[]): string | null {
  for (const f of figures ?? []) {
    for (const p of [f.page_image_path, f.video_asset, f.audio_asset]) {
      if (!p) continue;
      const m = SLUG_RE.exec(p);
      if (m && m[1]) {
        try {
          return decodeURIComponent(m[1]);
        } catch {
          return m[1];
        }
      }
    }
  }
  return null;
}

/** URL for a section-level teaching video: tutorial_assets/{slug}/video/section_{id}.mp4 */
export function sectionVideoUrl(slug: string, sectionId: number): string {
  return TutorialReadAPI.assetUrl(`tutorial_assets/${slug}/video/section_${sectionId}.mp4`);
}

/** URL for the section video poster (same key, .jpg). */
export function sectionPosterUrl(slug: string, sectionId: number): string {
  return TutorialReadAPI.assetUrl(`tutorial_assets/${slug}/video/section_${sectionId}.jpg`);
}
