import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AudioPlayer from './AudioPlayer';

describe('AudioPlayer', () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
    vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {});
    vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('sets normalized volume (0.5) on load and play toggle', () => {
    render(<AudioPlayer src="/api/v1/tutorials/assets/demo.mp3" />);
    const audio = document.querySelector('audio') as HTMLAudioElement;
    expect(audio).not.toBeNull();
    expect(audio.volume).toBe(0.5);

    audio.volume = 1;
    fireEvent.click(screen.getByRole('button', { name: '播放' }));
    expect(audio.volume).toBe(0.5);
  });
});
