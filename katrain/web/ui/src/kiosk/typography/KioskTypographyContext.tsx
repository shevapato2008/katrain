import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';

export type KioskChineseFont = 'wenkai' | 'kaiti' | 'lishu' | 'heiti';
export type KioskFontSize = 'large' | 'medium' | 'small';
export type TypographyPreference = { font: KioskChineseFont; size: KioskFontSize };

export const DEFAULT_TYPOGRAPHY: TypographyPreference = { font: 'wenkai', size: 'large' };
const ENDPOINT = '/api/v1/kiosk-preferences/typography';

const fontFaces: Record<KioskChineseFont, string> = {
  wenkai: '"SmartBox Kai"',
  kaiti: '"SmartBox CNS Kai"',
  lishu: '"SmartBox DaoLi"',
  heiti: '"SmartBox Noto Sans CJK"',
};
const sizeSteps: Record<KioskFontSize, string> = { large: '0px', medium: '2px', small: '4px' };

function isPreference(value: unknown): value is TypographyPreference {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.font === 'string' && candidate.font in fontFaces
    && typeof candidate.size === 'string' && candidate.size in sizeSteps;
}

async function readPreference(): Promise<TypographyPreference> {
  const response = await fetch(ENDPOINT);
  if (!response.ok) throw new Error(`GET typography: ${response.status}`);
  const value: unknown = await response.json();
  if (!isPreference(value)) throw new Error('Invalid typography preference');
  return value;
}

async function writePreference(value: TypographyPreference): Promise<void> {
  const response = await fetch(ENDPOINT, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value),
  });
  if (!response.ok) throw new Error(`PUT typography: ${response.status}`);
}

type TypographyContextValue = {
  preference: TypographyPreference;
  setPreference: (change: Partial<TypographyPreference>) => void;
  loading: boolean;
  saving: boolean;
  error: string | null;
  retry: () => void;
};
const TypographyContext = createContext<TypographyContextValue | null>(null);

export function useKioskTypography(): TypographyContextValue {
  const value = useContext(TypographyContext);
  if (!value) throw new Error('useKioskTypography requires KioskTypographyProvider');
  return value;
}

/** One device preference, shared by guests and signed-in kiosk routes. */
export function KioskTypographyProvider({ children, language }: { children: ReactNode; language: string }) {
  const [preference, setPreferenceState] = useState(DEFAULT_TYPOGRAPHY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readFailed, setReadFailed] = useState(false);
  const current = useRef(preference);
  const editGeneration = useRef(0);
  const saveQueue = useRef(Promise.resolve());

  useEffect(() => {
    let active = true;
    const initialGeneration = editGeneration.current;
    readPreference().then(value => {
      if (active && editGeneration.current === initialGeneration) {
        current.current = value;
        setPreferenceState(value);
        setReadFailed(false);
      }
    }).catch(() => {
      if (active) {
        setReadFailed(true);
        setError('字体设置暂时无法读取；当前使用默认值。');
      }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const enqueueSave = useCallback((value: TypographyPreference) => {
    setSaving(true);
    saveQueue.current = saveQueue.current.catch(() => undefined).then(async () => {
      try {
        await writePreference(value);
        if (current.current === value) { setError(null); setSaving(false); }
      } catch {
        if (current.current === value) {
          setError('字体设置未保存，请重试。');
          setSaving(false);
        }
      }
    });
  }, []);

  const setPreference = useCallback((change: Partial<TypographyPreference>) => {
    const next = { ...current.current, ...change };
    if (!isPreference(next) || (next.font === current.current.font && next.size === current.current.size)) return;
    editGeneration.current += 1;
    current.current = next;
    setPreferenceState(next);
    setReadFailed(false);
    setError(null);
    enqueueSave(next);
  }, [enqueueSave]);

  const retry = useCallback(() => {
    if (!readFailed) { enqueueSave(current.current); return; }
    const generation = editGeneration.current;
    setSaving(true);
    readPreference().then(value => {
      if (editGeneration.current !== generation) return;
      current.current = value;
      setPreferenceState(value);
      setReadFailed(false);
      setError(null);
    }).catch(() => {
      if (editGeneration.current === generation) setError('字体设置暂时无法读取；请重试。');
    }).finally(() => setSaving(false));
  }, [enqueueSave, readFailed]);

  // Portals inherit from body; the kiosk frame inherits the same value without a
  // page-wide font declaration. Restore prior inline values on route teardown.
  useLayoutEffect(() => {
    const style = document.body.style;
    const oldFont = style.getPropertyValue('--kiosk-cjk-font');
    const oldStep = style.getPropertyValue('--kiosk-size-step');
    const oldScope = document.body.getAttribute('data-kiosk-typography');
    const oldSize = document.body.getAttribute('data-kiosk-font-size');
    document.body.setAttribute('data-kiosk-typography', '');
    return () => {
      if (oldFont) style.setProperty('--kiosk-cjk-font', oldFont);
      else style.removeProperty('--kiosk-cjk-font');
      if (oldStep) style.setProperty('--kiosk-size-step', oldStep);
      else style.removeProperty('--kiosk-size-step');
      if (oldScope === null) document.body.removeAttribute('data-kiosk-typography');
      else document.body.setAttribute('data-kiosk-typography', oldScope);
      if (oldSize === null) document.body.removeAttribute('data-kiosk-font-size');
      else document.body.setAttribute('data-kiosk-font-size', oldSize);
    };
  }, []);
  useLayoutEffect(() => {
    const chineseUI = language === 'cn' || language === 'tw';
    document.body.style.setProperty('--kiosk-cjk-font', chineseUI ? fontFaces[preference.font] : fontFaces.wenkai);
    document.body.style.setProperty('--kiosk-size-step', sizeSteps[preference.size]);
    document.body.setAttribute('data-kiosk-font-size', preference.size);
  }, [language, preference]);

  return <TypographyContext.Provider value={{ preference, setPreference, loading, saving, error, retry }}>
    {children}
  </TypographyContext.Provider>;
}
