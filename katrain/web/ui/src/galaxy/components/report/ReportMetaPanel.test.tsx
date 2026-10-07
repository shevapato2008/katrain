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
  expect(within(dialog).getByText('分析规则', { exact: true }).parentElement).toHaveTextContent('—');
  expect(dialog).not.toHaveTextContent('已核验');
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

it('shows the verified event rule in metadata and details while retaining the wire and SGF rules', () => {
  render(<ThemeProvider theme={createGalaxyTheme('cn')}><ReportMetaPanel professional game={{ ...game, rules: 'japanese' }}
    analysisParameters={{ version: 1, verified: true, rules: 'japanese', komi: 6.5, sgf_sha256: 'sgf', parameter_sha256: 'params',
      provenance: { source: 'verified_evidence', evidence: { event_rules: 'korean' } } }}
    task={{ status: 'completed', report_type: 'deep' }} currentMove={0} currentAnalysis={null} /></ThemeProvider>);
  expect(screen.getByTestId('report-meta-panel')).toHaveTextContent('韩国规则');
  fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText('规则', { exact: true }).parentElement).toHaveTextContent('韩国规则');
  expect(within(dialog).getByText('SGF 规则').parentElement).toHaveTextContent('japanese');
  expect(within(dialog).getByText('分析规则（已核验）').parentElement).toHaveTextContent('日本规则');
});

it.each([['japanese', 6.5, '日本规则'], ['chinese', 7.5, '中国规则']] as const)('shows default %s provenance in existing details without verified labels', (rules, komi, label) => {
  render(<ThemeProvider theme={createGalaxyTheme('cn')}><ReportMetaPanel professional game={{ ...game, rules: 'chinese', komi }}
    analysisParameters={{ version: 3, verified: false, rules, komi, sgf_sha256: 'sgf', parameter_sha256: 'params',
      provenance: { source: 'komi_default', raw_rules: null, raw_komi: String(komi), policy: 'komi-default-v1' } }}
    task={{ status: 'completed', report_type: 'deep' }} currentMove={0} currentAnalysis={null} /></ThemeProvider>);
  expect(screen.getByTestId('report-meta-panel')).toHaveTextContent(`${label}（默认）`);
  fireEvent.click(screen.getByRole('button', { name: '对局详情' }));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).getByText('SGF 规则').parentElement).toHaveTextContent('—');
  expect(within(dialog).getByText('SGF 贴目').parentElement).toHaveTextContent(String(komi));
  expect(within(dialog).getByText('分析规则', { exact: true }).parentElement).toHaveTextContent(`${label}（默认）`);
  expect(within(dialog).getByText('分析贴目', { exact: true }).parentElement).toHaveTextContent(String(komi));
  expect(within(dialog).getByText('规则来源').parentElement).toHaveTextContent(`SGF 未记录规则；按贴目 ${komi} 默认采用${label}，未核验赛事实际规则。`);
  expect(dialog).not.toHaveTextContent('已核验');
});
