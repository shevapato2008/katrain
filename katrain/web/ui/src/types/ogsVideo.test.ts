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
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe('OGS video release contract', () => {
  it('uses the approved full production arrangement release', () => {
    expect(OGS_VIDEO_MANIFEST_URL).toBe('https://modelstella.com/media/tutorial_demos/ogs-full-20261117/manifest.json');
  });
  it('allows a poster-free production clip while keeping both profile URLs scoped to the release', () => {
    const full = structuredClone(manifest);
    Reflect.deleteProperty(full.clips[0], 'poster_url');
    Object.assign(full.clips[0].profiles, { 'galaxy-4k-v1': {
      url: `${OGS_VIDEO_BASE}clips/4278/galaxy-4k-v1.mp4`, width: 3840, height: 2160,
    } });
    expect(() => parseOgsVideoManifest(full)).not.toThrow();
    Object.assign(full.clips[0].profiles, { 'galaxy-4k-v1': {
      url: 'https://go.sailorvoyage.top/test.mp4', width: 3840, height: 2160,
    } });
    expect(() => parseOgsVideoManifest(full)).toThrow();
  });
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

const TEST_MEDIA_PREFIX = 'https://go.sailorvoyage.top/media/tutorial_assets/';
const TEST_MANIFEST_URL = '/arrangement/test-manifest.json';
const testManifest = {
  schema_version: 1, release_id: 'ogs-full-test-20261117', language: 'zh-cn',
  clips: [{ id: 4278, title: '四口气', book: '入门篇·上卷', page: 13, duration: 30,
    profiles: {
      'kiosk-7-v1': { url: `${TEST_MEDIA_PREFIX}intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4`, width: 1024, height: 600 },
      'galaxy-4k-v1': { url: `${TEST_MEDIA_PREFIX}intro-up/media/3d65c7ee44254be3a9fa9edede660118/video-2d-galaxy-4k-v1.mp4`, width: 3840, height: 2160 },
    } }],
  playlists: { 'count-liberties': [4278] },
};

async function loadTestPlayer(overrides: Record<string, string | undefined> = {}) {
  vi.stubEnv('VITE_OGS_TEST_MANIFEST_URL', TEST_MANIFEST_URL);
  vi.stubEnv('VITE_OGS_TEST_MEDIA_PREFIX', TEST_MEDIA_PREFIX);
  vi.stubEnv('VITE_OGS_TEST_API_BASE', '/api/v1/tutorials');
  for (const [key, value] of Object.entries(overrides)) vi.stubEnv(key, value);
  vi.resetModules();
  return import('./ogsVideo');
}

describe('trusted TEST video configuration', () => {
  it('accepts existing immutable TEST profiles and all configured lessons without posters', async () => {
    const player = await loadTestPlayer();
    const full = { ...testManifest, playlists: Object.fromEntries(Array.from({ length: 248 }, (_, i) => [`lesson-${i}`, [4278]])) };
    const parsed = player.parseOgsVideoManifest(full);
    expect(Object.keys(parsed.playlists)).toHaveLength(248);
    expect(player.videosForLesson(parsed, 'lesson-247')[0].profiles['kiosk-7-v1'].url).toContain(TEST_MEDIA_PREFIX);
    expect(player.OGS_VIDEO_MANIFEST_URL).toBe(TEST_MANIFEST_URL);
  });

  it('fetches only the build-configured manifest without credentials', async () => {
    await loadTestPlayer();
    const { TutorialReadAPI: testApi } = await import('../api/tutorialApi');
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(testManifest)));
    vi.stubGlobal('fetch', fetch);
    await testApi.getOgsVideoManifest();
    expect(fetch).toHaveBeenCalledWith(TEST_MANIFEST_URL,
      { signal: undefined, credentials: 'omit', referrerPolicy: 'no-referrer' });
  });

  it.each([
    'http://127.0.0.1:18951/arrangement/test-manifest.json',
    'https://go.sailorvoyage.top/media/tutorial_demos/ogs-full-test-20261117/manifest.json',
  ])('accepts a trusted preview manifest at %s', async url => {
    const player = await loadTestPlayer({ VITE_OGS_TEST_MANIFEST_URL: url });
    expect(player.OGS_VIDEO_MANIFEST_URL).toBe(url);
  });

  it('accepts a normalized TEST poster and rejects an untrusted poster', async () => {
    const player = await loadTestPlayer();
    const withPoster = structuredClone(testManifest) as typeof testManifest & { clips: Array<{ poster_url?: string }> };
    withPoster.clips[0].poster_url = `${TEST_MEDIA_PREFIX}intro-up/posters/4278.jpg`;
    expect(() => player.parseOgsVideoManifest(withPoster)).not.toThrow();
    withPoster.clips[0].poster_url = `${OGS_VIDEO_BASE}posters/4278.jpg`;
    expect(() => player.parseOgsVideoManifest(withPoster)).toThrow();
  });

  it.each([
    'https://example.com/media/tutorial_assets/intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4',
    'https://user:secret@go.sailorvoyage.top/media/tutorial_assets/intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4',
    `${TEST_MEDIA_PREFIX}intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4?token=secret`,
    `${TEST_MEDIA_PREFIX}intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4#fragment`,
    `${TEST_MEDIA_PREFIX}intro-up/../intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4`,
    `${TEST_MEDIA_PREFIX}intro-up/%2e%2e/intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-kiosk-7-v1.mp4`,
    `${TEST_MEDIA_PREFIX}intro-up/media/b0148e55478746b3886eddb2d950b6d2/video-2d-galaxy-4k-v1.mp4`,
    `${TEST_MEDIA_PREFIX}intro-up/media/not-an-immutable-task/video-2d-kiosk-7-v1.mp4`,
  ])('rejects a TEST media URL outside the configured generated-asset path: %s', async url => {
    const player = await loadTestPlayer();
    const broken = structuredClone(testManifest);
    broken.clips[0].profiles['kiosk-7-v1'].url = url;
    expect(() => player.parseOgsVideoManifest({ ...broken, media_prefix: 'https://example.com/' })).toThrow();
  });

  it('rejects unsupported profiles, wrong dimensions, malformed numbers and unknown references', async () => {
    const player = await loadTestPlayer();
    const badProfile = structuredClone(testManifest);
    Object.assign(badProfile.clips[0].profiles, { 'unknown-v1': badProfile.clips[0].profiles['kiosk-7-v1'] });
    expect(() => player.parseOgsVideoManifest(badProfile)).toThrow();
    for (const patch of [{ id: 0 }, { page: 1.5 }, { duration: NaN }, { duration: Infinity }, { duration: -1 }]) {
      expect(() => player.parseOgsVideoManifest({ ...testManifest, clips: [{ ...testManifest.clips[0], ...patch }] })).toThrow();
    }
    const wrongDimensions = structuredClone(testManifest);
    wrongDimensions.clips[0].profiles['galaxy-4k-v1'].width = 1024;
    expect(() => player.parseOgsVideoManifest(wrongDimensions)).toThrow();
    expect(() => player.parseOgsVideoManifest({ ...testManifest, playlists: { lesson: [999] } })).toThrow();
  });

  it.each([
    { VITE_OGS_TEST_MEDIA_PREFIX: undefined },
    { VITE_OGS_TEST_MEDIA_PREFIX: 'https://example.com/media/tutorial_assets/' },
    { VITE_OGS_TEST_MANIFEST_URL: 'https://example.com/manifest.json' },
    { VITE_OGS_TEST_MANIFEST_URL: '/arrangement/../manifest.json' },
    { VITE_OGS_TEST_MANIFEST_URL: '/arrangement/test-manifest.json?token=secret' },
    { VITE_OGS_TEST_MANIFEST_URL: 'http://user:secret@127.0.0.1:18951/arrangement/test-manifest.json' },
    { VITE_OGS_TEST_API_BASE: 'https://modelstella.com/api/v1/tutorials' },
  ])('rejects partial or unsafe build configuration: %j', async overrides => {
    await expect(loadTestPlayer(overrides)).rejects.toThrow('Invalid OGS TEST configuration');
  });
});
