/** Read-only, versioned lesson-to-video contract, independent of database IDs. */
export const OGS_VIDEO_BASE = 'https://modelstella.com/media/tutorial_demos/ogs-full-20261117/';
const TEST_ORIGIN = 'https://go.sailorvoyage.top';
const TEST_MEDIA_PREFIX = `${TEST_ORIGIN}/media/tutorial_assets/`;

function cleanUrl(value: unknown): URL | null {
  if (typeof value !== 'string' || !value || /[\s%\\?#]/.test(value)
    || /(?:^|\/)\.{1,2}(?:\/|$)/.test(value)) return null;
  try {
    const url = new URL(value, TEST_ORIGIN);
    if (url.username || url.password || url.search || url.hash || url.pathname.includes('//')) return null;
    if (value.startsWith('/') && !value.startsWith('//') && url.pathname === value) return url;
    return url.href === value ? url : null;
  } catch { return null; }
}

// Only build-time settings select the TEST environment. Neither the manifest nor
// location/search parameters participate in this trust decision. Require the
// complete configuration so an incomplete preview cannot silently read PROD.
function testConfiguration() {
  const manifest = import.meta.env.VITE_OGS_TEST_MANIFEST_URL;
  const mediaPrefix = import.meta.env.VITE_OGS_TEST_MEDIA_PREFIX;
  const apiBase = import.meta.env.VITE_OGS_TEST_API_BASE;
  if (manifest === undefined && mediaPrefix === undefined && apiBase === undefined) return null;
  const url = cleanUrl(manifest);
  if (mediaPrefix !== TEST_MEDIA_PREFIX || !url || !url.pathname.endsWith('.json')
    || !(manifest.startsWith('/') || url.origin === TEST_ORIGIN
      || (url.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(url.hostname)))
    || !['/api/v1/tutorials', `${TEST_ORIGIN}/api/v1/tutorials`].includes(apiBase)) {
    throw new Error('Invalid OGS TEST configuration');
  }
  return { manifest, apiBase };
}

const testConfig = testConfiguration();
export const OGS_VIDEO_MANIFEST_URL = testConfig?.manifest ?? `${OGS_VIDEO_BASE}manifest.json`;
export const OGS_TEST_API_BASE = testConfig?.apiBase;

export interface OgsLessonVideo {
  id: number;
  title: string;
  book: string;
  page: number;
  duration: number;
  poster_url?: string;
  profiles: {
    'kiosk-7-v1': { url: string; width: number; height: number };
    'galaxy-4k-v1'?: { url: string; width: number; height: number };
  };
}

function testAssetUrl(value: unknown, path: RegExp): boolean {
  return typeof value === 'string' && !!cleanUrl(value)
    && value.startsWith(TEST_MEDIA_PREFIX) && path.test(value.slice(TEST_MEDIA_PREFIX.length));
}

function testClipMedia(clip: OgsLessonVideo): boolean {
  if (!clip.profiles || typeof clip.profiles !== 'object' || Array.isArray(clip.profiles)) return false;
  if (clip.poster_url !== undefined && !testAssetUrl(clip.poster_url,
    /^[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_.-]+)*\.(?:jpg|jpeg|png|webp)$/)) return false;
  return Object.entries(clip.profiles).every(([name, profile]) => {
    const dimensions = name === 'kiosk-7-v1' ? [1024, 600] : name === 'galaxy-4k-v1' ? [3840, 2160] : null;
    return dimensions !== null && profile?.width === dimensions[0] && profile.height === dimensions[1]
      && testAssetUrl(profile.url, new RegExp(`^[a-z0-9][a-z0-9_-]*/media/[a-f0-9]{32}/video-2d-${name}\\.mp4$`));
  });
}

function productionClipMedia(clip: OgsLessonVideo): boolean {
  if (!clip.profiles || typeof clip.profiles !== 'object' || Array.isArray(clip.profiles)) return false;
  if (clip.poster_url !== undefined && clip.poster_url !== `${OGS_VIDEO_BASE}posters/${clip.id}.jpg`) return false;
  return Object.entries(clip.profiles).every(([name, profile]) => {
    const dimensions = name === 'kiosk-7-v1' ? [1024, 600] : name === 'galaxy-4k-v1' ? [3840, 2160] : null;
    return dimensions !== null && profile?.width === dimensions[0] && profile.height === dimensions[1]
      && profile.url === `${OGS_VIDEO_BASE}clips/${clip.id}/${name}.mp4`;
  });
}

export interface OgsVideoManifest {
  schema_version: 1;
  release_id: string;
  language: string;
  clips: OgsLessonVideo[];
  playlists: Record<string, number[]>;
}

export function parseOgsVideoManifest(input: unknown): OgsVideoManifest {
  const data = input as OgsVideoManifest | null;
  if (!data || data.schema_version !== 1 || typeof data.release_id !== 'string'
    || (testConfig && typeof data.language !== 'string')
    || !Array.isArray(data.clips) || !data.playlists || typeof data.playlists !== 'object'
    || Array.isArray(data.playlists)) throw new Error('Invalid OGS video manifest');
  const ids = new Set<number>();
  for (const clip of data.clips) {
    const profile = clip?.profiles?.['kiosk-7-v1'];
    if (!Number.isSafeInteger(clip?.id) || clip.id <= 0 || ids.has(clip.id)
      || typeof clip.title !== 'string' || typeof clip.book !== 'string'
      || !Number.isSafeInteger(clip.page) || clip.page <= 0
      || !Number.isFinite(clip.duration) || clip.duration <= 0
      || !profile || profile.width !== 1024 || profile.height !== 600
      || (testConfig ? !testClipMedia(clip) : !productionClipMedia(clip))) throw new Error('Invalid OGS kiosk video');
    ids.add(clip.id);
  }
  if (Object.values(data.playlists).some(list =>
    !Array.isArray(list) || list.some(id => !ids.has(id)))) throw new Error('Invalid OGS video playlist');
  return data;
}

export function videosForLesson(manifest: OgsVideoManifest | null, lessonId?: string): OgsLessonVideo[] {
  if (!manifest || !lessonId || !Object.prototype.hasOwnProperty.call(manifest.playlists, lessonId)) return [];
  return manifest.playlists[lessonId].flatMap(id => {
    const clip = manifest.clips.find(item => item.id === id);
    return clip ? [clip] : [];
  });
}
