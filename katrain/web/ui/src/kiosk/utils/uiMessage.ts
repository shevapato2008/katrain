import { interpolate } from './interpolate';
import { platformErrorMessage } from './platformErrorMessage';

export interface UiMessage {
  key: string;
  fallback: string;
  values?: Record<string, string | number>;
  error?: unknown;
}
export function uiMessage(key: string, fallback: string, values?: Record<string, string | number>): UiMessage {
  return { key, fallback, values };
}
export function uiError(error: unknown, key: string, fallback: string): UiMessage {
  return { key, fallback, error };
}
/** Keep a reason and parameters in state, and resolve it with the current language at render. */
export function renderUiMessage(value: UiMessage | string | null, t: (key: string, fallback?: string) => string): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  const copy = interpolate(t(value.key, value.fallback), value.values ?? {});
  if (value.error && typeof value.error === 'object' && 'key' in value.error && 'fallback' in value.error
    && typeof value.error.key === 'string' && typeof value.error.fallback === 'string') return renderUiMessage(value.error as UiMessage, t);
  return value.error === undefined ? copy : platformErrorMessage(value.error, copy, t);
}
