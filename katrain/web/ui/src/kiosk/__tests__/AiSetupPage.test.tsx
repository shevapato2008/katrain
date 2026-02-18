import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from '../pages/AiSetupPage';

const renderPage = (mode = 'free') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/ai/setup/${mode}`]}>
        <Routes>
          <Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('AiSetupPage', () => {
  it('renders board size options', () => {
    renderPage();
    expect(screen.getByText('棋盘')).toBeInTheDocument();
    expect(screen.getByText('9路')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
  });

  it('renders ruleset selector', () => {
    renderPage();
    expect(screen.getByText('规则')).toBeInTheDocument();
    expect(screen.getByText('中国')).toBeInTheDocument();
    expect(screen.getByText('日本')).toBeInTheDocument();
    expect(screen.getByText('韩国')).toBeInTheDocument();
    expect(screen.getByText('AGA')).toBeInTheDocument();
  });

  it('renders color selection', () => {
    renderPage();
    expect(screen.getByText(/黑/)).toBeInTheDocument();
    expect(screen.getByText(/白/)).toBeInTheDocument();
  });

  it('renders start button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始对弈/i })).toBeInTheDocument();
  });

  it('shows AI strategy selector for free mode', () => {
    renderPage('free');
    expect(screen.getByText('AI 策略')).toBeInTheDocument();
    expect(screen.getByText('拟人')).toBeInTheDocument();
    expect(screen.getByText('KataGo')).toBeInTheDocument();
    expect(screen.getByText('实地')).toBeInTheDocument();
    expect(screen.getByText('厚势')).toBeInTheDocument();
    expect(screen.getByText('策略')).toBeInTheDocument();
  });

  it('shows rank slider in free mode when human strategy selected', () => {
    renderPage('free');
    // Default strategy is ai:human, so rank slider should be visible
    expect(screen.getByText(/AI 棋力/)).toBeInTheDocument();
  });

  it('hides rank slider in free mode for non-human strategy', async () => {
    renderPage('free');
    const user = userEvent.setup();
    // Click KataGo strategy to switch away from ai:human
    await user.click(screen.getByText('KataGo'));
    expect(screen.queryByText(/AI 棋力/)).not.toBeInTheDocument();
  });

  it('hides AI strategy selector for ranked mode', () => {
    renderPage('ranked');
    expect(screen.queryByText('AI 策略')).not.toBeInTheDocument();
  });

  it('shows rank slider for ranked mode', () => {
    renderPage('ranked');
    expect(screen.getByText(/AI 棋力/)).toBeInTheDocument();
  });

  it('renders handicap slider', () => {
    renderPage();
    expect(screen.getByText(/让子: 无/)).toBeInTheDocument();
  });

  it('shows komi slider in free mode with no handicap', () => {
    renderPage('free');
    expect(screen.getByText(/贴目/)).toBeInTheDocument();
  });

  it('hides komi slider when handicap is set', () => {
    renderPage('free');
    // Find the handicap slider (the one after "让子" label) and change it
    const handicapSlider = screen.getByText(/让子: 无/).closest('[class*="MuiBox"]')!.querySelector('input[type="range"]')!;
    fireEvent.change(handicapSlider, { target: { value: 2 } });
    expect(screen.queryByText(/贴目/)).not.toBeInTheDocument();
  });

  it('shows time switch label', () => {
    renderPage();
    expect(screen.getByText('用时')).toBeInTheDocument();
  });

  it('hides time options when switch is off in free mode', () => {
    renderPage('free');
    // Switch is off by default in free mode
    expect(screen.queryByText(/主时间/)).not.toBeInTheDocument();
    expect(screen.queryByText(/读秒时间/)).not.toBeInTheDocument();
    expect(screen.queryByText(/读秒次数/)).not.toBeInTheDocument();
  });

  it('shows time options when switch is toggled on in free mode', async () => {
    renderPage('free');
    const user = userEvent.setup();
    const toggle = screen.getByLabelText('用时');
    await user.click(toggle);
    expect(screen.getByText(/主时间/)).toBeInTheDocument();
    expect(screen.getByText(/读秒时间/)).toBeInTheDocument();
    expect(screen.getByText(/读秒次数/)).toBeInTheDocument();
  });

  it('shows time options forced on for ranked mode', () => {
    renderPage('ranked');
    expect(screen.getByText(/主时间/)).toBeInTheDocument();
    expect(screen.getByText(/读秒时间/)).toBeInTheDocument();
    expect(screen.getByText(/读秒次数/)).toBeInTheDocument();
  });

  it('renders byoyomi time slider marks', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByLabelText('用时'));
    expect(screen.getByText('10秒')).toBeInTheDocument();
    expect(screen.getByText('30秒')).toBeInTheDocument();
    expect(screen.getByText('60秒')).toBeInTheDocument();
  });

  it('renders byoyomi period slider marks', async () => {
    renderPage('free');
    const user = userEvent.setup();
    await user.click(screen.getByLabelText('用时'));
    expect(screen.getByText('1次')).toBeInTheDocument();
    expect(screen.getByText('3次')).toBeInTheDocument();
    expect(screen.getByText('5次')).toBeInTheDocument();
  });
});
