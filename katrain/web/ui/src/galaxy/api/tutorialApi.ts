import type {
  TutorialCategory,
  TutorialExample,
  TutorialProgress,
  TutorialTopic,
  ProgressUpdate,
} from '../types/tutorial';

const BASE = '/api/v1/tutorials';

async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`Tutorial API ${resp.status}: ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Tutorial API ${resp.status}: ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

export const TutorialAPI = {
  getCategories: (): Promise<TutorialCategory[]> => apiGet('/categories'),

  getTopics: (categorySlug: string): Promise<TutorialTopic[]> =>
    apiGet(`/categories/${categorySlug}/topics`),

  getTopic: (topicId: string): Promise<TutorialTopic> => apiGet(`/topics/${topicId}`),

  getTopicExamples: (topicId: string): Promise<TutorialExample[]> =>
    apiGet(`/topics/${topicId}/examples`),

  getExample: (exampleId: string): Promise<TutorialExample> =>
    apiGet(`/examples/${exampleId}`),

  /** Build the URL for a published asset (image or audio). */
  assetUrl: (assetRef: string): string =>
    `${BASE}/assets/${assetRef.replace(/^assets\//, '')}`,

  getProgress: (): Promise<TutorialProgress[]> => apiGet('/progress'),

  updateProgress: (exampleId: string, update: ProgressUpdate): Promise<TutorialProgress> =>
    apiPost(`/progress/${exampleId}`, update),
};
