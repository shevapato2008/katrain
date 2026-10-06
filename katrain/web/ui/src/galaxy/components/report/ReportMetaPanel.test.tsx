import { fireEvent, render, screen, within } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { expect, it } from 'vitest';
import ReportMetaPanel from './ReportMetaPanel';
import { createGalaxyTheme } from '../../theme';

const game = { game_date: null, source: 'kifu_library', event: '赛事', title: null, round_name: null,
  result: null, rules: null, player_black: '黑方', player_white: '白方', black_rank: null, white_rank: null, komi: 6.5 };

it('keeps missing rules unresolved and shows raw komi without an invented winrate', () => {
  render(<ThemeProvider theme={createGalaxyTheme('cn')}><ReportMetaPanel professional game={game}
    task={{ status: 'rules_unresolved', report_type: 'deep' }} currentMove={0} currentAnalysis={null} /></ThemeProvider>);
  expect(screen.getByTestId('report-meta-panel')).toHaveTextContent('规则待核验');
  expect(screen.getByTestId('report-meta-panel')).not.toHaveTextContent('50.0%');
  fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText('SGF 贴目').parentElement).toHaveTextContent('6.5');
  expect(within(dialog).getByText('分析规则（已核验）').parentElement).toHaveTextContent('—');
  expect(dialog).toHaveStyle({ fontFamily: createGalaxyTheme('cn').typography.fontFamily });
});

it('uses version 2 corrected parameters for the report and preserves raw SGF values in details', () => {
  render(<ThemeProvider theme={createGalaxyTheme('cn')}><ReportMetaPanel professional game={{ ...game, rules: 'chinese' }}
    analysisParameters={{ version: 2, verified: true, rules: 'japanese', komi: 0, sgf_sha256: 'sgf', parameter_sha256: 'params', provenance: {} }}
    task={{ status: 'completed', report_type: 'deep' }} currentMove={0} currentAnalysis={null} /></ThemeProvider>);
  expect(screen.getByTestId('report-meta-panel')).toHaveTextContent('日本规则');
  expect(screen.getByTestId('report-meta-panel')).toHaveTextContent('分析贴目 0');
  fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText('SGF 规则').parentElement).toHaveTextContent('chinese');
  expect(within(dialog).getByText('SGF 贴目').parentElement).toHaveTextContent('6.5');
  expect(within(dialog).getByText('分析贴目（已核验）').parentElement).toHaveTextContent('0');
});

it.each([['new zealand', '新西兰规则'], ['aga-button', 'AGA Button 规则']])('labels verified %s without a rule fallback', (rules, label) => {
  render(<ThemeProvider theme={createGalaxyTheme('cn')}><ReportMetaPanel professional game={game}
    analysisParameters={{ version: 1, verified: true, rules, komi: 7.5, sgf_sha256: 'sgf', parameter_sha256: 'params', provenance: {} }}
    task={{ status: 'completed', report_type: 'deep' }} currentMove={0} currentAnalysis={null} /></ThemeProvider>);
  expect(screen.getByTestId('report-meta-panel')).toHaveTextContent(label);
  expect(screen.getByTestId('report-meta-panel')).not.toHaveTextContent('规则待核验');
});
