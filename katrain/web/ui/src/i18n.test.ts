import { beforeEach, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ getTranslations: vi.fn(), live: vi.fn() }));
vi.mock('./api', () => ({ API: { getTranslations: mocks.getTranslations } }));
vi.mock('./api/live', () => ({ LiveAPI: { getTranslations: mocks.live } }));

beforeEach(() => { vi.resetModules(); vi.clearAllMocks(); localStorage.clear(); });

it('中文首次加载不使用临时英文，也不等直播译名才通知页面', async () => {
  mocks.getTranslations.mockResolvedValue({ translations: { hello: '你好' } });
  mocks.live.mockReturnValue(new Promise(() => {}));
  const { i18n } = await import('./i18n');
  expect(i18n.lang).toBe('cn');
  const changed = vi.fn();
  i18n.subscribe(changed);
  await i18n.loadTranslations('cn');
  expect(changed).toHaveBeenCalled();
  expect(i18n.t('hello')).toBe('你好');
});

it('does not let an older language response overwrite the latest translation', async () => {
  let finish!: (value: { translations: Record<string, string> }) => void;
  mocks.getTranslations.mockImplementation((lang: string) => lang === 'jp' ? new Promise(resolve => { finish = resolve; }) : Promise.resolve({ translations: { hello: '안녕' } }));
  mocks.live.mockResolvedValue({});
  const { i18n } = await import('./i18n');
  const old = i18n.loadTranslations('jp');
  await i18n.loadTranslations('ko');
  finish({ translations: { hello: 'こんにちは' } });
  await old;
  expect(i18n.lang).toBe('ko');
  expect(i18n.t('hello')).toBe('안녕');
});

it('does not apply translations after their authoritative refresh was aborted', async () => {
  let finish!: (value: { translations: Record<string, string> }) => void;
  mocks.getTranslations.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const { i18n } = await import('./i18n');
  const abort = new AbortController();
  const pending = i18n.loadTranslations('jp', abort.signal);
  abort.abort();
  finish({ translations: { hello: 'こんにちは' } });
  expect(await pending).toBe(false);
  expect(i18n.lang).toBe('cn');
});
