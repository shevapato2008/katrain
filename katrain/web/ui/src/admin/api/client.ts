import type { SGFPayload } from '../../components/tutorials/SGFBoard';
import type { CronJobsResponse, CronQueuesResponse, CronRunsResponse } from '../cron/types';
import type { VisionStatus, VisionDevices, VisionMode, VisionGeometry, VisionImport, VisionCaptureInput, VisionFrame, VisionSessionList, VisionSession, VisionPreview, VisionSampleReview, VisionFreezeParameters, VisionFrozen, KifuAlbumList, KifuAlbumDetail, VisionFiducialMode, VisionAutoCheck, VisionModels, DiagnosticsStatus, DiagnosticsSnapshot } from '../vision/types';
import type { TrainingStatus, TrainingDataset, TrainingPresets, TrainingRun, TrainingModel, TrainingStartInput } from '../vision/training/types';

export interface TutorialCategory { slug: string; title: string; book_count: number }
export interface TutorialBook { id: number; category: string; title: string; slug: string; chapter_count: number }
export interface TutorialChapter { id: number; book_id: number; title: string; chapter_number: string; order: number }
export interface TutorialBookDetail extends TutorialBook { chapters: TutorialChapter[] }
export interface TutorialSection { id: number; chapter_id: number; title: string; section_number: string; order: number; figure_count: number }
export interface TutorialFigure {
  id: number;
  section_id: number;
  page: number;
  figure_label: string;
  book_text: string | null;
  page_context_text: string | null;
  page_image_path: string | null;
  board_payload: SGFPayload | null;
  recognition_debug: { human_verified?: boolean; [key: string]: unknown } | null;
  narration: string | null;
  audio_asset: string | null;
  video_asset: string | null;
  updated_at: string | null;
  order: number;
}
export interface TutorialSectionDetail extends TutorialSection { figures: TutorialFigure[] }
export interface VersionedRequest { expected_updated_at: string | null }
export interface VerifyResult {
  figure: TutorialFigure;
  training_export: { status: 'exported' | 'skipped' | 'failed'; count: number; reason?: string };
}

export interface GrafanaDashboard { id: string; title: string; url: string }
export interface PerformanceConfig { state: 'unconfigured' | 'invalid' | 'configured'; error: string | null; origin: string | null; dashboards: GrafanaDashboard[]; env: string }
export class AdminApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export function tutorialAssetUrl(assetPath: string | null): string | null {
  if (!assetPath) return null;
  const parts = assetPath.split('/').filter(Boolean);
  if (parts.some((part) => part === '..' || part === '.')) return null;
  return `/api/v1/tutorials/assets/${parts.map(encodeURIComponent).join('/')}`;
}

export function createAdminApi(fetcher: typeof fetch = fetch, token: () => string | null = () => null) {
  async function request<T>(url: string, init: RequestInit = {}, admin = false): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body) headers.set('Content-Type', 'application/json');
    if (admin) {
      const value = token();
      if (value) headers.set('Authorization', `Bearer ${value}`);
    }
    let response: Response;
    try {
      response = await fetcher(url, { ...init, headers });
    } catch (cause) {
      if (init.signal?.aborted || (cause instanceof DOMException && cause.name === 'AbortError')) throw cause;
      throw new AdminApiError(0, '网络连接失败，请重试。');
    }
    if (!response.ok) {
      let detail = `请求失败（${response.status}）`;
      try {
        const body = await response.json() as { detail?: unknown };
        if (typeof body.detail === 'string') detail = body.detail;
      } catch { /* Non-JSON error response. */ }
      throw new AdminApiError(response.status, detail);
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
  const publicRead = <T>(path: string) => request<T>(`/api/v1/tutorials${path}`);
  const adminRequest = <T>(path: string, init?: RequestInit) => request<T>(`/api/admin${path}`, init, true);
  const body = (value: unknown) => JSON.stringify(value);
  const vision = <T>(path: string, signal?: AbortSignal, value?: unknown, post = false) => adminRequest<T>(`/vision${path}`, {
    signal, cache: 'no-store', ...(post ? { method: 'POST' } : {}), ...(value !== undefined ? { body: body(value) } : {}),
  });
  const training = <T>(path: string, signal?: AbortSignal, value?: unknown) => adminRequest<T>(`/vision-training${path}`, {
    signal, cache: 'no-store', ...(value !== undefined ? { method: 'POST', body: body(value) } : {}),
  });
  return {
    login: (username: string, password: string) => request<{ access_token: string; token_type: string }>('/api/admin/auth/login', { method: 'POST', body: body({ username, password }) }),
    me: () => adminRequest<{ username: string; env: string }>('/auth/me'),
    logout: () => adminRequest<void>('/auth/logout', { method: 'POST' }),
    cronJobs: () => adminRequest<CronJobsResponse>('/cron/jobs'),
    cronQueues: () => adminRequest<CronQueuesResponse>('/cron/queues'),
    cronRuns: (name: string, limit = 50) => adminRequest<CronRunsResponse>(`/cron/jobs/${encodeURIComponent(name)}/runs?limit=${Math.min(200, Math.max(1, Math.trunc(limit)))}`),
    performance: (signal?: AbortSignal) => adminRequest<PerformanceConfig>('/performance', { signal, cache: 'no-store' }),
    kifuSearch: (q: string, signal?: AbortSignal) => adminRequest<KifuAlbumList>(`/kifu/albums?${new URLSearchParams({ ...(q.trim() ? { q: q.trim().slice(0, 100) } : {}), page_size: '30' })}`, { signal, cache: 'no-store' }),
    kifuAlbum: (id: number, signal?: AbortSignal) => adminRequest<KifuAlbumDetail>(`/kifu/albums/${Math.trunc(id)}`, { signal, cache: 'no-store' }),
    visionStatus: (signal?: AbortSignal) => vision<VisionStatus>('/status', signal),
    visionDevices: (signal?: AbortSignal) => vision<VisionDevices>('/devices', signal),
    visionConnect: (device_id: number, mode: VisionMode, signal?: AbortSignal) => vision<VisionStatus>('/connect', signal, { device_id, mode }, true),
    visionDisconnect: (signal?: AbortSignal) => vision<VisionStatus>('/disconnect', signal, undefined, true),
    visionCalibrate: (empty_confirmed: boolean, signal?: AbortSignal) => vision<VisionGeometry>('/calibrate', signal, { empty_confirmed }, true),
    visionImportSgf: (sgf: string, signal?: AbortSignal) => vision<VisionImport>('/sgf', signal, { sgf }, true),
    visionImportKifu: (album_id: number, signal?: AbortSignal) => vision<VisionImport>('/sgf/kifu', signal, { album_id }, true),
    visionCapture: (input: VisionCaptureInput, signal?: AbortSignal) => vision<VisionFrame>('/capture', signal, input, true),
    visionSessions: (signal?: AbortSignal) => vision<VisionSessionList>('/sessions', signal),
    visionSession: (id: string, signal?: AbortSignal) => vision<VisionSession>(`/sessions/${encodeURIComponent(id)}`, signal),
    visionResumeSession: (id: string, signal?: AbortSignal) => vision<VisionStatus>(`/sessions/${encodeURIComponent(id)}/resume`, signal, undefined, true),
    visionVerifyGeometry: (game_id: string, frame_id: string, overlay_confirmed: boolean, signal?: AbortSignal) => vision<VisionGeometry>('/verify-geometry', signal, { game_id, frame_id, overlay_confirmed }, true),
    visionPreview: (signal?: AbortSignal) => vision<VisionPreview>('/preview', signal),
    visionRemovalGuide: (game_id: string, move_index: number, signal?: AbortSignal) => vision<{ game_id: string; move_index: number; points: { row: number; col: number }[] }>('/removal-guide', signal, { game_id, move_index }, true),
    visionUndo: (id: string, frame_id: string, signal?: AbortSignal) => vision<{ session: VisionSession; led_restored: boolean }>(`/sessions/${encodeURIComponent(id)}/undo`, signal, { frame_id, operator_confirmed: true }, true),
    visionEnd: (id: string, signal?: AbortSignal) => vision<{ session: VisionSession; led_restored: boolean }>(`/sessions/${encodeURIComponent(id)}/end`, signal, { operator_confirmed: true }, true),
    visionLedTest: (signal?: AbortSignal) => vision<{ points: { row: number; col: number }[]; guidance_restored: boolean | null }>('/led-test', signal, { operator_confirmed: true }, true),
    visionFiducial: (mode: VisionFiducialMode, signal?: AbortSignal) => vision<VisionStatus>('/fiducial', signal, { mode }, true),
    visionAutoCheck: (game_id: string, move_index: number, signal?: AbortSignal) => vision<VisionAutoCheck>('/auto-check', signal, { game_id, move_index }, true),
    visionModels: (signal?: AbortSignal) => vision<VisionModels>('/models', signal),
    visionActivateModel: (model_id: string, signal?: AbortSignal) => vision<VisionModels>('/models/activate', signal, { model_id, confirmed: true }, true),
    visionRollbackModel: (signal?: AbortSignal) => vision<VisionModels>('/models/rollback', signal, { confirmed: true }, true),
    diagnosticsStatus: (signal?: AbortSignal) => vision<DiagnosticsStatus>('/diagnostics/status', signal),
    diagnosticsSnapshot: (signal?: AbortSignal) => vision<DiagnosticsSnapshot>('/diagnostics/snapshot', signal),
    diagnosticsStart: (signal?: AbortSignal) => vision<DiagnosticsStatus>('/diagnostics/start', signal, { confirmed: true }, true),
    diagnosticsStop: (signal?: AbortSignal) => vision<DiagnosticsStatus>('/diagnostics/stop', signal, undefined, true),
    visionReviewSample: (id: string, frame: string, signal?: AbortSignal) => vision<VisionSampleReview>(`/sessions/${encodeURIComponent(id)}/frames/${encodeURIComponent(frame)}/review`, signal),
    visionFreezeSession: (id: string, parameters: VisionFreezeParameters = {}, signal?: AbortSignal) => vision<VisionFrozen>(`/sessions/${encodeURIComponent(id)}/freeze`, signal, parameters, true),
    trainingStatus: (signal?: AbortSignal) => training<TrainingStatus>('/status', signal),
    trainingDatasets: (signal?: AbortSignal) => training<TrainingDataset[]>('/datasets', signal),
    trainingPresets: (signal?: AbortSignal) => training<TrainingPresets>('/presets', signal),
    trainingRuns: (signal?: AbortSignal) => training<TrainingRun[]>('/runs', signal),
    trainingRun: (id: string, signal?: AbortSignal) => training<TrainingRun>(`/runs/${encodeURIComponent(id)}`, signal),
    trainingModels: (signal?: AbortSignal) => training<TrainingModel[]>('/models', signal),
    trainingStart: (input: TrainingStartInput, signal?: AbortSignal) => training<TrainingRun>('/runs', signal, input),
    trainingCancel: (id: string, confirmed: boolean, signal?: AbortSignal) => training<TrainingRun>(`/runs/${encodeURIComponent(id)}/cancel`, signal, { confirmed }),
    categories: () => publicRead<TutorialCategory[]>('/categories'),
    books: (category: string) => publicRead<TutorialBook[]>(`/categories/${encodeURIComponent(category)}/books`),
    book: (id: number) => publicRead<TutorialBookDetail>(`/books/${id}`),
    sections: (chapterId: number) => publicRead<TutorialSection[]>(`/chapters/${chapterId}/sections`),
    section: (sectionId: number) => publicRead<TutorialSectionDetail>(`/sections/${sectionId}`),
    figure: (figureId: number) => publicRead<TutorialFigure>(`/figures/${figureId}`),
    saveBoard: (figureId: number, update: VersionedRequest & { board_payload: SGFPayload; narration?: string }) => adminRequest<TutorialFigure>(`/tutorials/figures/${figureId}/board`, { method: 'PUT', body: body(update) }),
    saveNarration: (figureId: number, update: VersionedRequest & { narration: string }) => adminRequest<TutorialFigure>(`/tutorials/figures/${figureId}/narration`, { method: 'PUT', body: body(update) }),
    generateAudio: (figureId: number, update: VersionedRequest & { narration: string }) => adminRequest<TutorialFigure>(`/tutorials/figures/${figureId}/generate-audio`, { method: 'POST', body: body(update) }),
    verify: (figureId: number, update: VersionedRequest) => adminRequest<VerifyResult>(`/tutorials/figures/${figureId}/verify`, { method: 'PUT', body: body(update) }),
  };
}
