import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KioskDock } from './KioskDock';
import { KioskTopbar } from './KioskTopbar';
const locale = vi.hoisted(() => ({ lang: 'cn' }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ lang: locale.lang, t: (_key: string, fallback: string) => fallback }) }));
describe('Go shell follows the current device UI language', () => {
  it.each([
    ['cn', '对弈', '主页', '围棋'], ['tw', '對弈', '主頁', '圍棋'], ['en', 'Play', 'Home', 'Go'], ['jp', '対局', 'ホーム', '囲碁'], ['ko', '대국', '홈', '바둑'],
  ])('%s localizes navigation without changing routes or brand', (lang, play, home, go) => {
    locale.lang = lang;
    render(<><KioskTopbar identity={{}} onHome={() => {}} /><KioskDock pathname="/kiosk/play" onTab={() => {}} /></>);
    expect(screen.getByRole('button', { name: play })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByTestId('kiosk-home-action')).toHaveTextContent(home);
    expect(screen.getByText(go)).toBeInTheDocument();
    expect(screen.getByTestId('kiosk-brand-zh')).toHaveTextContent('智星盒');
  });
});
