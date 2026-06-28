import { describe, it, expect } from 'vitest';
import { bookSlugFromFigures, sectionVideoUrl, sectionPosterUrl } from './tutorialAssets';
import type { TutorialFigure } from '../types/tutorial';

const fig = (over: Partial<TutorialFigure>): TutorialFigure =>
  ({ id: 1, section_id: 1, page: 1, figure_label: '图1', book_text: null, page_context_text: null,
     bbox: null, page_image_path: null, board_payload: null, recognition_debug: null, narration: null,
     audio_asset: null, video_asset: null, video_duration_ms: null, video_size_bytes: null,
     order: 0, updated_at: null, ...over });

describe('bookSlugFromFigures', () => {
  it('parses slug from page_image_path', () => {
    expect(bookSlugFromFigures([fig({ page_image_path: 'tutorial_assets/zhongguo-weiqi-shi/page/page_1.jpg' })]))
      .toBe('zhongguo-weiqi-shi');
  });
  it('parses slug from video_asset', () => {
    expect(bookSlugFromFigures([fig({ video_asset: 'tutorial_assets/abc/video/fig_7.mp4' })])).toBe('abc');
  });
  it('parses slug from audio_asset', () => {
    expect(bookSlugFromFigures([fig({ audio_asset: 'tutorial_assets/abc/audio/fig_7.mp3' })])).toBe('abc');
  });
  it('skips empty first path, uses later figure', () => {
    expect(bookSlugFromFigures([fig({}), fig({ page_image_path: 'tutorial_assets/xyz/page/page_2.jpg' })])).toBe('xyz');
  });
  it('returns null when prefix missing', () => {
    expect(bookSlugFromFigures([fig({ page_image_path: 'something/else/page_1.jpg' })])).toBeNull();
  });
  it('returns null for empty slug segment', () => {
    expect(bookSlugFromFigures([fig({ page_image_path: 'tutorial_assets//page/page_1.jpg' })])).toBeNull();
  });
  it('decodes URL-encoded slug', () => {
    expect(bookSlugFromFigures([fig({ page_image_path: 'tutorial_assets/a%20b/page/p.jpg' })])).toBe('a b');
  });
  it('returns null for empty figures array', () => {
    expect(bookSlugFromFigures([])).toBeNull();
  });
  it('returns null for undefined figures', () => {
    expect(bookSlugFromFigures(undefined as unknown as TutorialFigure[])).toBeNull();
  });
});

describe('section URLs', () => {
  it('builds section video url', () => {
    expect(sectionVideoUrl('abc', 42)).toBe('/api/v1/tutorials/assets/tutorial_assets/abc/video/section_42.mp4');
  });
  it('builds section poster url', () => {
    expect(sectionPosterUrl('abc', 42)).toBe('/api/v1/tutorials/assets/tutorial_assets/abc/video/section_42.jpg');
  });
});
