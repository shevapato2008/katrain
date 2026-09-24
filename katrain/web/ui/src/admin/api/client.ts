import type { SGFPayload } from '../../components/tutorials/SGFBoard';

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
    } catch {
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
  return {
    login: (username: string, password: string) => request<{ access_token: string; token_type: string }>('/api/admin/auth/login', { method: 'POST', body: body({ username, password }) }),
    me: () => adminRequest<{ username: string; env: string }>('/auth/me'),
    logout: () => adminRequest<void>('/auth/logout', { method: 'POST' }),
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
