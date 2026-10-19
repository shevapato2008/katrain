import { describe, expect, it } from 'vitest';
import { selectTutorialVideoProfile } from './tutorialVideoProfile';
import type { TutorialFigure, OutputProfileSummary } from '../../types/tutorial';
const summary = (output_profile: OutputProfileSummary['output_profile']): OutputProfileSummary => ({ asset: `${output_profile}.mp4`, output_profile, width: 1024, height: 600, fps: 25, duration_ms: 6000, size_bytes: 100, playback_mode: 'static', timing_status: 'pending', timing_reason: null, renderer_recipe: 'approved' });
describe('tutorial video profile selection', () => {
  it('selects only the requested output profile even when the compatibility pointer differs', () => {
    const galaxy = summary('galaxy-4k-v1'); const kiosk = summary('kiosk-7-v1');
    const figure = { video_asset: 'legacy.mp4', video_output_profile: 'legacy', video_profiles: { 'galaxy-4k-v1': galaxy, 'kiosk-7-v1': kiosk } } as TutorialFigure;
    expect(selectTutorialVideoProfile(figure, 'galaxy-4k-v1')).toBe(galaxy);
    expect(selectTutorialVideoProfile(figure, 'kiosk-7-v1')).toBe(kiosk);
  });
  it('never falls back to Galaxy or legacy when the device profile is missing', () => {
    expect(selectTutorialVideoProfile({ video_asset: 'galaxy.mp4', video_output_profile: 'galaxy-4k-v1', video_profiles: { 'galaxy-4k-v1': summary('galaxy-4k-v1') } } as TutorialFigure, 'kiosk-7-v1')).toBeNull();
    expect(selectTutorialVideoProfile({ video_asset: 'legacy.mp4' } as TutorialFigure, 'galaxy-4k-v1')).toBeNull();
    expect(selectTutorialVideoProfile(null, 'kiosk-7-v1')).toBeNull();
  });
});
