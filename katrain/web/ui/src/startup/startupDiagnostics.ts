type FailureCategory = 'render' | 'preload';
type Surface = 'kiosk' | 'galaxy' | 'recording';
type FailureRecord = {
  buildId: string;
  timestamp: string;
  category: FailureCategory;
  surface: Surface;
};

const storageKey = 'katrain:startup-failures';
const maxRecords = 5;

// Production's emitted module filename contains the build's asset fingerprint.
// Never persist the module URL, development filesystem path, query or fragment.
function buildId(): string {
  const filename = new URL(import.meta.url).pathname.split('/').pop() ?? '';
  return /^[A-Za-z0-9_-]{1,80}\.js$/.test(filename)
    ? filename.slice(0, -3)
    : import.meta.env.PROD ? 'unknown' : 'development';
}

function safeSurface(): Surface {
  const path = window.location.pathname;
  if (__KIOSK_2D_ONLY__ || /^\/kiosk(?:\/|$)/.test(path)) return 'kiosk';
  return path === '/record' ? 'recording' : 'galaxy';
}

function allowedRecord(value: unknown): FailureRecord | null {
  if (!value || typeof value !== 'object') return null;
  const { buildId, timestamp, category, surface } = value as Record<string, unknown>;
  if (typeof buildId !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(buildId)
    || typeof timestamp !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(timestamp)
    || (category !== 'render' && category !== 'preload')
    || (surface !== 'kiosk' && surface !== 'galaxy' && surface !== 'recording')) return null;
  return { buildId, timestamp, category, surface };
}

// Intentionally accepts no Error, event, props, route or other application data.
export function recordStartupFailure(category: FailureCategory): void {
  if (category !== 'render' && category !== 'preload') return;
  try {
    const stored = window.sessionStorage.getItem(storageKey);
    let parsed: unknown = [];
    if (stored && stored.length <= 4096) {
      try { parsed = JSON.parse(stored); } catch { /* Discard corrupt prior records. */ }
    }
    const previous = Array.isArray(parsed)
      ? parsed.slice(-(maxRecords - 1)).map(allowedRecord).filter(record => record !== null)
      : [];
    const record: FailureRecord = {
      buildId: buildId(), timestamp: new Date().toISOString(), category, surface: safeSurface(),
    };
    window.sessionStorage.setItem(storageKey, JSON.stringify([...previous, record]));
  } catch {
    // Disabled storage, quota errors and corrupt prior data cannot break recovery UI.
  }
}
