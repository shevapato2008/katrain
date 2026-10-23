import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { OgsCourseIndex, OgsStep } from '../../types/ogsCourse';
import type { PhysicalTsumegoOptions } from '../hooks/usePhysicalTsumego';
import OgsCourseHomePage from './OgsCourseHomePage';
import OgsCourseChapterPage from './OgsCourseChapterPage';
import OgsCourseExercisePage from './OgsCourseExercisePage';
import TutorialCategoriesPage from './TutorialCategoriesPage';

const mocks = vi.hoisted(() => ({
  getCourse: vi.fn(), getStep: vi.fn(), getCategories: vi.fn(),
  vision: { enabled: false, recognitionReady: false },
  geometry: null as null | { status: { phase: string; session_calibrated: boolean; capabilities: { geometry_ready: boolean } } },
  physicalOptions: null as PhysicalTsumegoOptions | null,
  screenMove: vi.fn(),
}));
vi.mock('../../api/tutorialApi', () => ({ TutorialReadAPI: {
  getOgsCourse: (...args: unknown[]) => mocks.getCourse(...args),
  getOgsStep: (...args: unknown[]) => mocks.getStep(...args),
  getCategories: (...args: unknown[]) => mocks.getCategories(...args),
} }));
vi.mock('../context/VisionContext', () => ({ useVision: () => ({ visionStatus: mocks.vision }) }));
vi.mock('../context/GeometryContext', () => ({ useOptionalGeometry: () => mocks.geometry }));
vi.mock('../hooks/useVisionSync', () => ({ useVisionSync: () => ({ connected: true, syncEvents: [] }) }));
vi.mock('../hooks/usePhysicalTsumego', () => ({ usePhysicalTsumego: (options: PhysicalTsumegoOptions) => {
  mocks.physicalOptions = options;
  return { phase: options.enabled ? 'ready' : 'off', stage: null, missing: [], extra: [], stageMatched: 0, stageTotal: 0, ledOk: true, onScreenMove: mocks.screenMove };
} }));
vi.mock('../shell/KioskPagebar', () => ({ KioskPagebar: ({ onBack, title }: { onBack: () => void; title: string }) => <div><button onClick={onBack}>返回课程</button>{title}</div> }));
vi.mock('../shell/KioskScrollZone', () => ({ KioskScrollZone: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

const course: OgsCourseIndex = {
  book_id: 1, title: 'OGS 围棋入门与基础练习', source: { repository: 'OGS', commit: 'abc', locale_version: '1', license: 'AGPL-3.0' }, languages: ['zh-cn'],
  chapters: [{ id: 'fundamentals', number: 1, title: '入门知识', lesson_count: 1, step_count: 5 }],
  lessons: [{ id: 'bl4-opening-4', chapter_id: 'fundamentals', order: 1, course_code: '1.1', route: 'bl4-opening-4', title: '布局基础', subtext: '落子练习', step_count: 5, first_page: 1 }],
  counts: { chapters: 1, lessons: 1, steps: 5, languages: 1, screenshots: 0, exercise_kinds: { puzzle: 1, choice: 1, pass: 1, remove: 1, finish: 1 }, unsupported: 0 }, license_notice: '',
};
const base: OgsStep = {
  book_id: 1, figure_id: 1, source_id: 'bl4-opening-4:1', source_url: '', lesson_id: 'bl4-opening-4', step: 1, page: 1, size: 19,
  initial_player: 'W', stones: { B: [[1, 1]], W: [[3, 3]] }, viewport: { col: 0, row: 0, cols: 5, rows: 5 }, letters: { '2,3': 'A', '4,4': 'B' }, shapes: { '2,2': 'triangle' },
  exercise: { kind: 'puzzle', tree: { point: null, correct: false, wrong: false, children: [{ point: [2, 3], correct: true, wrong: false, children: [] }] } },
  locale: { requested: 'zh-cn', effective: 'zh-cn', text: { title: '布局基础', instruction: '白先，点 A 位。' } }, screenshot: null, screenshot_status: 'pending',
};
const steps: OgsStep[] = [base,
  { ...base, page: 2, step: 2, exercise: { kind: 'choice', choices: [{ value: '2', label_key: '2' }, { value: '3', label_key: '3' }], correct_choice: '3' } },
  { ...base, page: 3, step: 3, exercise: { kind: 'pass' } },
  { ...base, page: 4, step: 4, exercise: { kind: 'remove', remove_targets: [[1, 1]] } },
  { ...base, page: 5, step: 5, exercise: { kind: 'finish' } },
];
function renderAt(path: string) { return render(<MemoryRouter initialEntries={[path]}><Routes>
  <Route path="/kiosk/tutorial" element={<OgsCourseHomePage />} />
  <Route path="/kiosk/tutorial/chapter/:chapterId" element={<OgsCourseChapterPage />} />
  <Route path="/kiosk/tutorial/lesson/:lessonId" element={<OgsCourseExercisePage />} />
  <Route path="/kiosk/tutorial/library" element={<TutorialCategoriesPage />} />
</Routes></MemoryRouter>); }

beforeEach(() => {
  mocks.getCourse.mockReset().mockResolvedValue(course);
  mocks.getStep.mockReset().mockImplementation((page: number) => Promise.resolve(steps[page - 1]));
  mocks.getCategories.mockReset().mockResolvedValue([]);
  mocks.vision.enabled = false; mocks.vision.recognitionReady = false;
  mocks.geometry = null;
  mocks.physicalOptions = null; mocks.screenMove.mockReset();
});

describe('OGS course journey', () => {
  it('navigates home to chapter to lesson and uses full-board coordinates in a cropped white-to-play puzzle', async () => {
    renderAt('/kiosk/tutorial');
    fireEvent.click(await screen.findByRole('button', { name: /开始第一章/ }));
    fireEvent.click(await screen.findByRole('button', { name: /布局基础/ }));
    expect(await screen.findByText('白先，点 A 位。')).toBeInTheDocument();
    expect(screen.getByTestId('ogs-board')).toHaveAttribute('data-window', '5x5');
    expect(screen.getAllByText('A').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('ogs-point-2-3'));
    expect(screen.getByText('回答正确')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /下一步/ })).toBeEnabled();
  });

  it('handles choice, pass, remove, finish, retry and previous step', async () => {
    renderAt('/kiosk/tutorial/lesson/bl4-opening-4');
    await screen.findByText('白先，点 A 位。');
    fireEvent.click(screen.getByTestId('ogs-point-2-3'));
    fireEvent.click(screen.getByRole('button', { name: /下一步/ }));
    await waitFor(() => expect(screen.getByText('选出答案')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '2' }));
    expect(screen.getByText('再试一次')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    fireEvent.click(screen.getByRole('button', { name: '3' }));
    fireEvent.click(screen.getByRole('button', { name: /下一步/ }));
    await screen.findByRole('button', { name: '弃手' });
    fireEvent.click(screen.getByRole('button', { name: '弃手' }));
    fireEvent.click(screen.getByRole('button', { name: /下一步/ }));
    await screen.findByText('点选要拿除的棋块');
    fireEvent.click(screen.getByTestId('ogs-point-1-1'));
    fireEvent.click(screen.getByRole('button', { name: /下一步/ }));
    await screen.findByRole('button', { name: '确认终局' });
    fireEvent.click(screen.getByRole('button', { name: '确认终局' }));
    expect(screen.getByRole('button', { name: /完成本课/ })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: /上一步/ }));
    await screen.findByText('点选要拿除的棋块');
  });

  it('shows load failure and retry; legacy library keeps its back control in every state', async () => {
    mocks.getCourse.mockRejectedValueOnce(new Error('offline')).mockResolvedValue(course);
    renderAt('/kiosk/tutorial');
    expect(await screen.findByText('课程暂不可用')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(await screen.findByText('课程目录')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /其他教材/ }));
    expect(screen.getByRole('button', { name: '返回课程' })).toBeInTheDocument();
    expect(await screen.findByTestId('tutorial-empty')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '返回课程' }));
    expect(await screen.findByText('课程目录')).toBeInTheDocument();
  });

  it('gates physical board by kind, size and readiness, and uses the same judge for confirmed physical moves', async () => {
    const { rerender } = renderAt('/kiosk/tutorial/lesson/bl4-opening-4');
    await screen.findByText('白先，点 A 位。');
    expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(screen.getByTestId('ogs-physical-hint')).toHaveTextContent('未检测到摄像头');
    mocks.vision.enabled = true; mocks.vision.recognitionReady = true;
    rerender(<MemoryRouter initialEntries={['/kiosk/tutorial/lesson/bl4-opening-4']}><Routes><Route path="/kiosk/tutorial/lesson/:lessonId" element={<OgsCourseExercisePage />} /></Routes></MemoryRouter>);
    expect(screen.getByRole('button', { name: '实体盘' })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: '实体盘' }));
    expect(mocks.physicalOptions?.enabled).toBe(true);
    act(() => { expect(mocks.physicalOptions?.placeStone(2, 15)?.type).toBe('solved'); });
    expect(screen.getByText('回答正确')).toBeInTheDocument();
    expect(mocks.getStep).toHaveBeenCalledWith(1);
  });

  it.each([9, 13])('keeps physical board unavailable for a %i-line puzzle', async (size) => {
    mocks.vision.enabled = true; mocks.vision.recognitionReady = true;
    mocks.getStep.mockResolvedValueOnce({ ...base, size, viewport: null, stones: { B: [], W: [] } });
    renderAt('/kiosk/tutorial/lesson/bl4-opening-4');
    await screen.findByText('白先，点 A 位。');
    expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(screen.getByTestId('ogs-physical-hint')).toHaveTextContent('实体盘当前支持 19 路练习');
  });

  it('keeps physical board unavailable for a 19-line choice', async () => {
    mocks.vision.enabled = true; mocks.vision.recognitionReady = true;
    mocks.getStep.mockResolvedValueOnce({ ...base, exercise: steps[1].exercise });
    renderAt('/kiosk/tutorial/lesson/bl4-opening-4');
    await screen.findByText('选出答案');
    expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(screen.getByTestId('ogs-physical-hint')).toHaveTextContent('本步骤请在屏幕完成');
  });

  it('explains unconfirmed geometry and offers the calibration route', async () => {
    mocks.vision.enabled = true; mocks.vision.recognitionReady = true;
    mocks.geometry = { status: { phase: 'ready', session_calibrated: false, capabilities: { geometry_ready: true } } };
    renderAt('/kiosk/tutorial/lesson/bl4-opening-4');
    await screen.findByText('白先，点 A 位。');
    expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(screen.getByTestId('ogs-physical-hint')).toHaveTextContent('先确认棋盘标定');
    expect(screen.getByRole('button', { name: '去标定' })).toBeInTheDocument();
  });
});
