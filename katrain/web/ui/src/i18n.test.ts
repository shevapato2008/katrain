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

it('translates missing professional-library labels without waiting for a server catalog update', async () => {
  mocks.getTranslations.mockResolvedValue({ translations: {} });
  mocks.live.mockResolvedValue({});
  const { i18n } = await import('./i18n');
  for (const [language, selected, select, library, jump] of [
    ['cn', '选中这一局', '请选择棋谱', '职业棋谱', '跳转'],
    ['tw', '選中這一局', '請選擇棋譜', '職業棋譜', '跳轉'],
    ['en', 'Selected game', 'Select a game record', 'Professional game library', 'Go'],
    ['jp', '選択した対局', '棋譜を選んでください', 'プロ棋譜', '移動'],
    ['ko', '선택한 대국', '기보를 선택하세요', '프로 기보', '이동'],
  ]) {
    await i18n.loadTranslations(language);
    expect(i18n.t('kifu:selected_game', '选中这一局')).toBe(selected);
    expect(i18n.t('kifu:select_game', '请选择棋谱')).toBe(select);
    expect(i18n.t('kifu:professional_library', '职业棋谱')).toBe(library);
    expect(i18n.t('kifu:jump', '跳转')).toBe(jump);
  }
  mocks.getTranslations.mockResolvedValue({ translations: { 'kifu:selected_game': 'Server-owned wording' } });
  await i18n.loadTranslations('en');
  expect(i18n.t('kifu:selected_game')).toBe('Server-owned wording');
});
