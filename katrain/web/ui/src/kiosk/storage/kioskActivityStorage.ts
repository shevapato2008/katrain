/**
 * Kiosk client-side storage isolation shim — the 4th zero-persistence layer for box-SSO
 * guest mode (layers 1-3 are server-side: session ownership, write-block, zero-persistence
 * on logout). This closes the browser-storage leak: the kiosk chromium runs `--incognito`
 * (so localStorage/sessionStorage live only in the running chromium's RAM and are never
 * written to disk), but decision-B guest entry only NAVIGATES the browser — it never
 * restarts the chromium process — so a prior identity's in-RAM localStorage would otherwise
 * survive the switch and a guest would read it.
 *
 * `kioskActivityStorage(identityKey, isGuest)` is the pure factory:
 *   - guest, OR identityKey unresolved (null) -> an in-memory Map. NEVER touches
 *     localStorage/sessionStorage: nothing written here can reach disk, and nothing read
 *     here can be a prior real user's (or the legacy unscoped) data.
 *   - real user (identityKey = user.uuid)     -> localStorage, every key suffixed
 *     `${key}:${identityKey}` so two identities never collide.
 *
 * identityKey === null is ALSO the correct value while identity is still unresolved
 * (AuthContext.isLoading === true) — callers MUST treat "unresolved" the same as "guest"
 * for storage purposes. This closes the first-paint race: several call sites (e.g.
 * TsumegoProgressProvider, BaipuListPage) read synchronously in a useState/useMemo
 * initializer, before AuthContext's async /me probe has resolved who is actually looking
 * at the screen. Passing identityKey=null during that window guarantees the synchronous
 * read can never surface a real user's (or the legacy unscoped) data.
 */

export interface KioskActivityStorage {
  getItem(key: string): string | null;
  removeItem(key: string): void;
  setItem(key: string, value: string): void;
}

// Shared ephemeral backing for every guest / unresolved-identity instance during this JS
// runtime's lifetime. Sharing one Map across calls is intentional and safe: the invariant is
// "never touches disk", not "isolated per call" — any real navigation (the guest-bootstrap
// redirect round trip, or a plain page reload) throws away the whole JS module graph — and
// this Map with it — anyway, so nothing here ever outlives a single browsing session.
let guestMemory = new Map<string, string>();

function createMemoryStorage(backing: Map<string, string>): KioskActivityStorage {
  return {
    getItem: (key) => (backing.has(key) ? backing.get(key)! : null),
    setItem: (key, value) => {
      backing.set(key, value);
    },
    removeItem: (key) => {
      backing.delete(key);
    },
  };
}

function createNamespacedLocalStorage(identityKey: string): KioskActivityStorage {
  const scoped = (key: string) => `${key}:${identityKey}`;
  return {
    getItem: (key) => {
      try {
        return localStorage.getItem(scoped(key));
      } catch {
        return null;
      }
    },
    setItem: (key, value) => {
      try {
        localStorage.setItem(scoped(key), value);
      } catch {
        // best-effort cache; ignore quota/unavailable storage
      }
    },
    removeItem: (key) => {
      try {
        localStorage.removeItem(scoped(key));
      } catch {
        // ignore
      }
    },
  };
}

/**
 * Build the identity-scoped storage for the current caller. See module doc for the
 * guest/unresolved -> ephemeral, real-user -> namespaced-localStorage contract.
 */
export function kioskActivityStorage(identityKey: string | null, isGuest: boolean): KioskActivityStorage {
  if (isGuest || !identityKey) return createMemoryStorage(guestMemory);
  return createNamespacedLocalStorage(identityKey);
}

/**
 * One-time migration for a RESOLVED REAL identity: if a legacy UNSCOPED key still exists
 * (written before this identity-scoping layer existed) and the namespaced key does not yet
 * exist under `store`, copy it once, then delete the legacy key outright — so it can never
 * be read by (or migrated again for) the NEXT identity that uses this kiosk.
 *
 * Callers must only invoke this for a resolved real user (never for a guest / unresolved
 * identity) — guests must skip migration entirely: they must never read, consume, or delete
 * the legacy key (deleting it would itself be an observable side effect of a guest visit).
 */
export function migrateLegacyActivityKey(store: KioskActivityStorage, legacyKey: string): void {
  try {
    const legacyValue = localStorage.getItem(legacyKey);
    if (legacyValue === null) return;
    if (store.getItem(legacyKey) === null) {
      store.setItem(legacyKey, legacyValue);
    }
    // Always drop the legacy key once a real identity has observed it — whether we just
    // migrated it or the namespaced key already existed — so a *different* future identity
    // can never inherit it either.
    localStorage.removeItem(legacyKey);
  } catch {
    // best-effort; never throw out of a migration attempt
  }
}

// ---- Resolved-identity singleton --------------------------------------------------------
// A handful of call sites have no React component to thread identity through (plain module
// functions such as activeSession.ts, the TsumegoProgressContext default value used with no
// <TsumegoProgressProvider> ancestor, the baipuApi.ts cache helpers). AuthContext is the
// single writer: it calls setKioskIdentity() once /me resolves — and ONLY then (never while
// isLoading). Until that first call — and in any render tree that never mounts AuthProvider
// at all (e.g. an isolated unit test) — this defaults to the same ephemeral guest store, so
// every one of those call sites inherits "empty until resolved" for free.
let currentStore: KioskActivityStorage = createMemoryStorage(guestMemory);
let currentSignature: string | null = null;

export function setKioskIdentity(identityKey: string | null, isGuest: boolean): void {
  const signature = isGuest ? 'guest' : identityKey ? `user:${identityKey}` : null;
  if (signature === currentSignature) return;
  currentSignature = signature;
  currentStore = kioskActivityStorage(identityKey, isGuest);
}

export function getCurrentKioskActivityStorage(): KioskActivityStorage {
  return currentStore;
}

/** Test-only: reset both the shared ephemeral map and the resolved-identity singleton. */
export function __resetKioskActivityStorageForTests(): void {
  guestMemory = new Map<string, string>();
  currentStore = createMemoryStorage(guestMemory);
  currentSignature = null;
}
