import type { OutputProfile, OutputProfileSummary, TutorialFigure } from '../../types/tutorial';

/** A compatibility video pointer cannot establish an output profile's identity. */
export function selectTutorialVideoProfile(figure: TutorialFigure | null, profile: OutputProfile): OutputProfileSummary | null {
  const video = figure?.video_profiles?.[profile];
  return video?.asset && video.output_profile === profile ? video : null;
}

/** Explain calibration before playback; this status is not part of the rendered lesson. */
export function tutorialVideoCalibrationNote(video: OutputProfileSummary | null): string | null {
  if (!video || video.playback_mode !== 'static' || video.timing_status !== 'pending') return null;
  return `静态讲解·落子时间待校准${video.timing_reason ? `：${video.timing_reason}` : ''}`;
}
