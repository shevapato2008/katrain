import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AdminApp from './AdminApp';

const figure = {
  id: 4, section_id: 3, page: 8, figure_label: '图 1', book_text: '原书文字', page_context_text: null,
  page_image_path: 'tutorial_assets/book/pages/8.png', board_payload: { size: 19, stones: { B: [[3, 3]], W: [] }, labels: { '3,3': '1' } },
  recognition_debug: { human_verified: false }, narration: '旧讲解', audio_asset: null, video_asset: null,
  order: 1, updated_at: '2026-09-24T08:00:00Z',
};
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

describe('tutorial admin real workbench', () => {
  const fetchMock = vi.fn<typeof fetch>();
  let conflict = false;
  let sectionFigures: Array<Omit<typeof figure, 'board_payload'> & { board_payload: typeof figure.board_payload | null }>;
  let latestFigure: typeof sectionFigures[number] = figure;

  beforeEach(() => {
    localStorage.clear();
    conflict = false;
    sectionFigures = [figure];
    latestFigure = figure;
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input) => {
      const path = String(input);
      if (path === '/api/admin/auth/login') return json({ access_token: 'admin-token', token_type: 'bearer' });
      if (path === '/api/admin/auth/me') return json({ username: 'admin:fan', env: 'test' });
      if (path === '/api/v1/tutorials/categories') return json([{ slug: '入门', title: '入门', book_count: 1 }]);
      if (path === '/api/v1/tutorials/categories/%E5%85%A5%E9%97%A8/books') return json([{ id: 1, category: '入门', title: '实书', slug: 'book', chapter_count: 1 }]);
      if (path === '/api/v1/tutorials/books/1') return json({ id: 1, category: '入门', title: '实书', slug: 'book', chapter_count: 1, chapters: [{ id: 2, book_id: 1, title: '第一章', chapter_number: '1', order: 1 }] });
      if (path === '/api/v1/tutorials/chapters/2/sections') return json([{ id: 3, chapter_id: 2, title: '第一节', section_number: '1', order: 1, figure_count: 1 }]);
      if (path === '/api/v1/tutorials/sections/3') return json({ id: 3, chapter_id: 2, title: '第一节', section_number: '1', order: 1, figure_count: sectionFigures.length, figures: sectionFigures });
      if (path === '/api/v1/tutorials/figures/4') return json(latestFigure);
      if (path === '/api/admin/tutorials/figures/4/narration') return conflict ? json({ detail: 'Conflict' }, 409) : json({ ...figure, narration: '新讲解', updated_at: '2026-09-24T08:00:01Z' });
      if (path === '/api/admin/tutorials/figures/4/board') return conflict ? json({ detail: 'Conflict' }, 409) : json({ ...figure, board_payload: { size: 19, stones: { B: [], W: [] } }, updated_at: '2026-09-24T08:00:01Z' });
      throw new Error(`Unexpected request ${path}`);
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  async function signIn() {
    const user = userEvent.setup();
    render(<AdminApp />);
    await user.type(screen.getByLabelText('后台用户名'), 'admin:fan');
    await user.type(screen.getByLabelText('密码'), 'test-password');
    await user.click(screen.getByRole('button', { name: '登录' }));
    await screen.findByText('原书文字');
    return user;
  }

  it('signs in to the independent backend and saves real narration with a version', async () => {
    const user = await signIn();
    expect(screen.getByText('测试环境')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '编辑讲解' }));
    await user.clear(screen.getByRole('textbox', { name: '编辑语音讲解' }));
    await user.type(screen.getByRole('textbox', { name: '编辑语音讲解' }), '新讲解');
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    expect(await screen.findByText('新讲解')).toBeInTheDocument();
    const write = fetchMock.mock.calls.find(([path]) => path === '/api/admin/tutorials/figures/4/narration');
    expect(JSON.parse(String(write?.[1]?.body))).toEqual({ narration: '新讲解', expected_updated_at: figure.updated_at });
    expect(new Headers(write?.[1]?.headers).get('Authorization')).toBe('Bearer admin-token');
    expect(screen.queryByText(/本地演示/)).not.toBeInTheDocument();
  });

  it('reloads the server version after 409 without losing the draft, then retries with its version', async () => {
    conflict = true;
    latestFigure = { ...figure, narration: '其他人已修改', updated_at: '2026-09-24T08:00:02Z' };
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: '编辑讲解' }));
    await user.clear(screen.getByRole('textbox', { name: '编辑语音讲解' }));
    await user.type(screen.getByRole('textbox', { name: '编辑语音讲解' }), '未保存讲解');
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('刷新');
    expect(screen.getByRole('textbox', { name: '编辑语音讲解' })).toHaveValue('未保存讲解');
    await user.click(screen.getByRole('button', { name: '读取服务器版本' }));
    expect(await screen.findByText('其他人已修改')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: '编辑语音讲解' })).toHaveValue('未保存讲解');
    expect(screen.getByRole('button', { name: '保存更改' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: '确认以草稿覆盖服务器同字段内容' }));
    conflict = false;
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    const writes = fetchMock.mock.calls.filter(([path]) => path === '/api/admin/tutorials/figures/4/narration');
    expect(JSON.parse(String(writes.at(-1)?.[1]?.body)).expected_updated_at).toBe(latestFigure.updated_at);
  });

  it('rebases a narration-only draft on a concurrent board edit without reverting the board', async () => {
    conflict = true;
    latestFigure = { ...figure, board_payload: { size: 19, stones: { B: [[4, 4]], W: [] }, labels: { '4,4': '1' } }, updated_at: '2026-09-24T08:00:02Z' };
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: '编辑讲解' }));
    await user.clear(screen.getByRole('textbox', { name: '编辑语音讲解' }));
    await user.type(screen.getByRole('textbox', { name: '编辑语音讲解' }), '我的讲解');
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    await user.click(await screen.findByRole('button', { name: '读取服务器版本' }));
    conflict = false;
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    expect(fetchMock.mock.calls.filter(([path]) => path === '/api/admin/tutorials/figures/4/board')).toHaveLength(0);
    const writes = fetchMock.mock.calls.filter(([path]) => path === '/api/admin/tutorials/figures/4/narration');
    expect(JSON.parse(String(writes.at(-1)?.[1]?.body))).toEqual({ narration: '我的讲解', expected_updated_at: latestFigure.updated_at });
  });

  it('rebases a board initialization on concurrent narration without reverting its text', async () => {
    sectionFigures = [{ ...figure, board_payload: null }];
    latestFigure = { ...figure, board_payload: null, narration: '其他人的讲解', updated_at: '2026-09-24T08:00:02Z' };
    conflict = true;
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: '编辑棋图' }));
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    await user.click(await screen.findByRole('button', { name: '读取服务器版本' }));
    conflict = false;
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    const writes = fetchMock.mock.calls.filter(([path]) => path === '/api/admin/tutorials/figures/4/board');
    expect(JSON.parse(String(writes.at(-1)?.[1]?.body))).toEqual({
      board_payload: { size: 19, stones: { B: [], W: [] } }, expected_updated_at: latestFigure.updated_at,
    });
  });

  it('lets an operator initialize a figure whose board payload is null', async () => {
    sectionFigures = [{ ...figure, board_payload: null }];
    const user = await signIn();
    expect(screen.getByText('此图尚无棋盘，空盘仅作为编辑起点。')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '编辑棋图' }));
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    expect(await screen.findByText('更改已保存。')).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([path]) => path === '/api/admin/tutorials/figures/4/board')).toBe(true);
  });

  it('does not create a board when only narration is edited on a null-board figure', async () => {
    sectionFigures = [{ ...figure, board_payload: null }];
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: '编辑讲解' }));
    await user.clear(screen.getByRole('textbox', { name: '编辑语音讲解' }));
    await user.type(screen.getByRole('textbox', { name: '编辑语音讲解' }), '新讲解');
    await user.click(screen.getByRole('button', { name: '保存更改' }));
    expect(await screen.findByText('新讲解')).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([path]) => path === '/api/admin/tutorials/figures/4/board')).toBe(false);
  });

  it('shows an honest empty state when a section has no figures', async () => {
    sectionFigures = [];
    const user = userEvent.setup();
    render(<AdminApp />);
    await user.type(screen.getByLabelText('后台用户名'), 'admin:fan');
    await user.type(screen.getByLabelText('密码'), 'test-password');
    await user.click(screen.getByRole('button', { name: '登录' }));
    expect(await screen.findByText('当前小节没有棋图。')).toBeInTheDocument();
  });

  it('labels the review step as a manual acknowledgment, not a completed logic check', async () => {
    const user = await signIn();
    await user.click(screen.getByRole('button', { name: '人工核对完成' }));
    expect(screen.getByRole('status')).toHaveTextContent('已标记人工核对');
    expect(screen.getByRole('button', { name: '✓ 确认审核' })).toBeEnabled();
  });
});
