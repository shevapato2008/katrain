import { afterEach, describe, expect, it, vi } from 'vitest';
import { OGS_VIDEO_BASE, OGS_VIDEO_MANIFEST_URL, parseOgsVideoManifest, videosForLesson } from './ogsVideo';
import { TutorialReadAPI } from '../api/tutorialApi';

const manifest = {
  schema_version: 1, release_id: 'ogs-intro-20261115', language: 'zh-cn',
  clips: [{ id: 4278, title: '四口气', book: '入门篇·上卷', page: 13, duration: 30,
    poster_url: `${OGS_VIDEO_BASE}posters/4278.jpg`,
    profiles: { 'kiosk-7-v1': { url: `${OGS_VIDEO_BASE}clips/4278/kiosk-7-v1.mp4`, width: 1024, height: 600 } } }],
  playlists: { 'count-liberties': [4278] },
};
afterEach(() => vi.unstubAllGlobals());

describe('OGS video release contract', () => {
  it('maps by stable lesson identity and keeps unmapped lessons empty', () => {
    const parsed = parseOgsVideoManifest(manifest);
    expect(videosForLesson(parsed, 'count-liberties').map(c => c.id)).toEqual([4278]);
    expect(videosForLesson(parsed, 'eyes')).toEqual([]);
    expect(videosForLesson(parsed, 'toString')).toEqual([]);
  });
  it('rejects a broken playlist and media outside the fixed production release', () => {
    expect(() => parseOgsVideoManifest({ ...manifest, playlists: { eyes: [999] } })).toThrow();
    const broken = structuredClone(manifest);
    broken.clips[0].profiles['kiosk-7-v1'].url = 'https://go.sailorvoyage.top/test.mp4';
    expect(() => parseOgsVideoManifest(broken)).toThrow();
  });
  it('reads the published manifest without credentials or a hotlink referer', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(manifest)));
    vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    expect((await TutorialReadAPI.getOgsVideoManifest(controller.signal)).clips).toHaveLength(1);
    expect(fetch).toHaveBeenCalledWith(OGS_VIDEO_MANIFEST_URL,
      { signal: controller.signal, credentials: 'omit', referrerPolicy: 'no-referrer' });
  });
  it('reports a failed response instead of treating it as an empty directory', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('offline', { status: 503 })));
    await expect(TutorialReadAPI.getOgsVideoManifest()).rejects.toThrow('503');
  });
});
