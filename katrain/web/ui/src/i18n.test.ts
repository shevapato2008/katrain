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
