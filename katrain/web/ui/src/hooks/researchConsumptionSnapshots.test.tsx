import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GalaxyResearchPage from '../galaxy/pages/ResearchPage';
import KioskResearchPage from '../kiosk/pages/ResearchPage';

const mocks = vi.hoisted(() => ({ source: '', quote: vi.fn(), position: vi.fn() }));
vi.mock('../galaxy/context/GameNavigationContext', () => ({ useGameNavigation: () => ({ registerActiveGame: vi.fn(), unregisterActiveGame: vi.fn(), requestNavigation: vi.fn() }) }));
vi.mock('../context/AuthContext', () => ({ useAuth: () => ({ token: null, status: 'authenticated', identityKey: 'cookie-person', isAuthenticated: true, isGuest: false }) }));
vi.mock('../hooks/useTranslation', () => ({ useTranslation: () => ({ lang: 'cn', t: (_key: string, fallback: string) => fallback }) }));
vi.mock('../features/report/useReportTasks', () => ({ useReportTasks: () => ({ pendingQuote: null, quoteBusy: false, error: null }) }));
vi.mock('../api/userGamesApi', () => ({ UserGamesAPI: { get: async () => ({ id: 'game', sgf_content: mocks.source }), list: vi.fn() } }));
vi.mock('../galaxy/components/research/CloudSGFPanel', () => ({ default: () => null }));
vi.mock('../galaxy/components/auth/AuthRequiredDialog', () => ({ default: () => null }));
vi.mock('../galaxy/components/research/ResearchSetupPanel', () => ({ default: (props: { onPlaceModeChange: (mode: string) => void; onToggleHints: () => void; onToggleTerritory: () => void }) => <>
  <button onClick={() => props.onPlaceModeChange('black')}>摆黑</button><button onClick={props.onToggleHints}>支招</button><button onClick={props.onToggleTerritory}>领地</button>
</> }));
vi.mock('../components/live/LiveBoard', () => ({ default: (props: { onIntersectionClick: (x: number, y: number) => void; currentMove: number }) => <div data-testid="board" data-cursor={props.currentMove}><button onClick={() => props.onIntersectionClick(3, 3)}>D4</button><button onClick={() => props.onIntersectionClick(15, 15)}>Q16</button></div> }));
vi.mock('../api/membershipApi', () => ({ membershipApi: { getCatalog: async () => ({ membership_mode: 'enabled', capabilities: { quotes: true, positions: true } }),
  createQuote: (...args: unknown[]) => mocks.quote(...args), createPosition: (...args: unknown[]) => mocks.position(...args),
} }));
function canonical(sgf: string) {
  return JSON.parse(execFileSync('python3', ['-c', 'import json,sys; from katrain.web.core.billing_input import canonical_analysis_input; print(json.dumps(canonical_analysis_input(json.load(sys.stdin), "position", "normal")))'], {
    cwd: resolve(process.cwd(), '../../..'), input: JSON.stringify(sgf), encoding: 'utf8',
  })) as { initial_player: string; initial_stones: string[][]; moves: string[][] };
}
beforeEach(() => {
  vi.clearAllMocks();
  mocks.source = '';
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined);
  mocks.quote.mockImplementation(async ({ sgf }: { sgf: string }) => {
    canonical(sgf); // A malformed frontend snapshot must fail here, as it does on the real server.
    return { token: 'signed', kind: 'position', profile: 'normal', source: 'membership', wallet_max_display_points: '0.01' };
  });
  mocks.position.mockImplementation(async ({ sgf }: { sgf: string }) => {
    canonical(sgf);
    return { operation_id: 1, state: 'succeeded', result: { ownership: Array(361).fill(0), moves: [] } };
  });
});
for (const surface of ['galaxy', 'kiosk'] as const) {
  const page = surface === 'galaxy' ? <GalaxyResearchPage /> : <KioskResearchPage />;
  const renderPage = (suffix = '') => render(<MemoryRouter initialEntries={[`/${surface}/research${suffix}`]}>{page}</MemoryRouter>);
  describe(`${surface} paid setup snapshot`, () => {
    it('quotes and executes repeated black placement as setup, then reuses the result', async () => {
      renderPage();
      fireEvent.click(screen.getByRole('button', { name: '摆黑', exact: true }));
      fireEvent.click(screen.getByRole('button', { name: 'D4', exact: true }));
      fireEvent.click(screen.getByRole('button', { name: 'Q16', exact: true }));
      expect(screen.getByText('摆子编辑已建立新局面，原行棋历史已清除。')).toBeVisible();
      fireEvent.click(screen.getByRole('button', { name: '支招', exact: true }));
      await waitFor(() => expect(mocks.quote).toHaveBeenCalledTimes(1), { timeout: 3000 });
      await screen.findByRole('dialog', {}, { timeout: 3000 });
      expect(canonical(mocks.quote.mock.calls[0][0].sgf)).toMatchObject({ initial_stones: [['B', 'Q16'], ['B', 'D4']], initial_player: 'B', moves: [] });
      fireEvent.click(screen.getByRole('button', { name: '确认并开始', exact: true }));
      await waitFor(() => expect(mocks.position).toHaveBeenCalledTimes(1));
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
      // Kiosk has no candidates for this fixture, but territory itself still reuses the one result.
      fireEvent.click(screen.getByRole('button', { name: '领地', exact: true }));
      expect(mocks.position).toHaveBeenCalledTimes(1);
    });
    it('keeps imported setup, player, and complete history in both quote and execute', async () => {
      mocks.source = '(;SZ[19]KM[7.5]RU[chinese]AB[dp][pd]AW[dd]PL[W];W[pp];B[qq])';
      renderPage('?user_game_id=game');
      await waitFor(() => expect(screen.getByTestId('board')).toHaveAttribute('data-cursor', '5'));
      fireEvent.click(screen.getByRole('button', { name: '领地', exact: true }));
      await waitFor(() => expect(mocks.quote).toHaveBeenCalledTimes(1), { timeout: 3000 });
      await screen.findByRole('dialog', {}, { timeout: 3000 });
      const quoted = canonical(mocks.quote.mock.calls[0][0].sgf);
      expect(quoted).toMatchObject({ initial_player: 'W', initial_stones: [['B', 'Q16'], ['B', 'D4'], ['W', 'D16']], moves: [['W', 'Q4'], ['B', 'R3']] });
      fireEvent.click(screen.getByRole('button', { name: '确认并开始', exact: true }));
      await waitFor(() => expect(mocks.position).toHaveBeenCalledTimes(1));
      expect(mocks.position.mock.calls[0][0].sgf).toBe(mocks.quote.mock.calls[0][0].sgf);
    });
  });
}
