/** Read-only, versioned lesson-to-video contract, independent of database IDs. */
export const OGS_VIDEO_BASE = 'https://modelstella.com/media/tutorial_demos/ogs-intro-20261115/';
export const OGS_VIDEO_MANIFEST_URL = `${OGS_VIDEO_BASE}manifest.json`;

export interface OgsLessonVideo {
  id: number;
  title: string;
  book: string;
  page: number;
  duration: number;
  poster_url: string;
  profiles: {
    'kiosk-7-v1': { url: string; width: number; height: number };
  };
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
    || !Array.isArray(data.clips) || !data.playlists || typeof data.playlists !== 'object'
    || Array.isArray(data.playlists)) throw new Error('Invalid OGS video manifest');
  const ids = new Set<number>();
  for (const clip of data.clips) {
    const profile = clip?.profiles?.['kiosk-7-v1'];
    if (!Number.isSafeInteger(clip?.id) || clip.id <= 0 || ids.has(clip.id)
      || typeof clip.title !== 'string' || typeof clip.book !== 'string'
      || !Number.isSafeInteger(clip.page) || clip.page <= 0
      || !Number.isFinite(clip.duration) || clip.duration <= 0
      || clip.poster_url !== `${OGS_VIDEO_BASE}posters/${clip.id}.jpg`
      || profile?.url !== `${OGS_VIDEO_BASE}clips/${clip.id}/kiosk-7-v1.mp4`
      || profile.width !== 1024 || profile.height !== 600) throw new Error('Invalid OGS kiosk video');
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
