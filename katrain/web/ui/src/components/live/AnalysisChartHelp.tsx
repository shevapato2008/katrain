import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Box, IconButton, Popover, useTheme } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import CloseIcon from '@mui/icons-material/Close';
import { TIER_DEF_TEXT, BRILLIANCE_BANDS, BRILLIANCE_HELP_TEXT } from './chartDefinitions';
import { useTranslation } from '../../hooks/useTranslation';
import { GRADE_TIERS, PER_SIDE_LIMIT, type buildHistogram, type buildMatchRate, type selectPerSide } from '../../features/analysis/moveGrade';

export type AnalysisTab = 'trend' | 'brilliant' | 'mistake' | 'perf' | 'match';

/** Same definitions and count limitations beside both report surfaces' tabs. */
export function AnalysisHelpContent({ tab, selection, histogram, matchRate }: {
  tab: AnalysisTab;
  selection?: ReturnType<typeof selectPerSide>;
  histogram: ReturnType<typeof buildHistogram>;
  matchRate: ReturnType<typeof buildMatchRate>;
}) {
  const { t } = useTranslation();
  return <>
    {tab === 'trend' && <p>{t('report:trend_help', '绿线为黑方胜率，橙线为黑方领先目数。横轴为手数；点击图表跳转到对应局面，缺少分析的局面不补值。')}</p>}
    {tab === 'brilliant' && <>
      <p>{BRILLIANCE_HELP_TEXT(t).entry}</p>
      <p>{BRILLIANCE_HELP_TEXT(t).probability}</p>
      {BRILLIANCE_BANDS.map(({ level, band }) => <div key={level}>{t('grade:brilliance', '妙度')} {level} · {band}</div>)}
    </>}
    {(tab === 'mistake' || tab === 'perf') && <>
      {GRADE_TIERS.map(tier => <p key={tier.id}><strong>{t(tier.i18nKey, tier.zh)}</strong> · {TIER_DEF_TEXT(t)[tier.id]}</p>)}
      <p>{t('grade:unrated', '未评级')} · {TIER_DEF_TEXT(t).unrated}</p>
    </>}
    {(tab === 'brilliant' || tab === 'mistake') && <>
      <p>{t('grade:axis_aria', '，黑方在轴上方、白方在下方，横轴是手数').replace(/^[，,]/, '')}</p>
      <p>{t('grade:pick_hint', '点图上任一手看详情')}</p>
      <p>{t('grade:count_note', '本阶段共 {n} 处').replace('{n}', String(selection?.total ?? 0))} · {t('grade:truncated_plot', '图上每方最多画 {k} 条，另有 {n} 处未画出').replace('{k}', String(PER_SIDE_LIMIT)).replace('{n}', String(selection?.truncated ?? 0))}</p>
    </>}
    {tab === 'perf' && <p>{t('grade:histogram_footer', '黑 {b} 手 / 白 {w} 手已评级').replace('{b}', String(histogram.blackTotal)).replace('{w}', String(histogram.whiteTotal))} · {t('grade:histogram_unrated', '{n} 手未评级').replace('{n}', String(histogram.unrated))}<br />{t('grade:histogram_aria', '七档发挥水准分布，黑柱为黑方、白柱为白方，各自归一')}</p>}
    {tab === 'match' && <>
      <p>{t('grade:match_timeline_legend', '满格实色 = 走中一选，半高浅色 = 进前三，底色 = 其他')}</p>
      {matchRate.rows.map(row => <p key={row.id}>{t(row.i18nKey, row.zh)} · {t('review:black', '黑')} {row.black}/{row.blackTotal} · {t('review:white', '白')} {row.white}/{row.whiteTotal}</p>)}
      <p>{t('grade:match_footer', '分母是能与 AI 比对的手数：黑 {b} 手 / 白 {w} 手').replace('{b}', String(matchRate.blackDecided)).replace('{w}', String(matchRate.whiteDecided))} · {t('grade:match_undecidable', '{n} 手无法比对').replace('{n}', String(matchRate.undecidable))}</p>
      <p>{t('grade:match_caveat', '一致率高低取决于局面难度，不能单独当作棋力或作弊的证据。')}</p>
    </>}
  </>;
}

export function ChartTabHelp({ label, children, active = true }: { label: string; children: ReactNode; active?: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [anchor, setAnchor] = useState<HTMLButtonElement | null>(null);
  const clear = () => { clearTimeout(timer.current); };
  useEffect(() => () => clearTimeout(timer.current), []);
  const style = anchor ? getComputedStyle(anchor) : null;
  return <>
    <IconButton className={`chart-tab-help${active ? '' : ' chart-tab-help--inactive'}`}
      aria-label={`${label} · ${t('report:chart_help', '说明')}`} aria-expanded={!!anchor} aria-haspopup="dialog"
      onMouseEnter={event => { const target = event.currentTarget; clear(); timer.current = setTimeout(() => setAnchor(target), 550); }}
      onMouseLeave={clear} onClick={event => { clear(); setAnchor(anchor ? null : event.currentTarget); }}
      sx={{ width: 44, height: 44, p: 0, pl: '4px', justifyContent: 'flex-start', flexShrink: 0, fontFamily: 'inherit', color: 'inherit', '& svg': { fontSize: 20 } }}><InfoOutlinedIcon /></IconButton>
    <Popover open={!!anchor} anchorEl={anchor} onClose={() => { clear(); setAnchor(null); }}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      slotProps={{ paper: { role: 'dialog', 'aria-label': `${label} · ${t('report:chart_help', '说明')}`,
        sx: { p: 2, width: 380, maxWidth: 'calc(100vw - 24px)', maxHeight: 'calc(100vh - 32px)', boxSizing: 'border-box',
          fontFamily: style?.fontFamily || theme.typography.fontFamily, fontSize: 14, lineHeight: 1.6,
          bgcolor: style?.getPropertyValue('--panel').trim() || 'background.paper', color: style?.getPropertyValue('--text').trim() || 'text.primary',
          border: '1px solid', borderColor: 'primary.main', '& p': { my: 1 } } } }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><strong>{label}</strong><IconButton aria-label={t('common:close', '关闭')} onClick={() => setAnchor(null)} sx={{ width: 44, height: 44, color: 'inherit' }}><CloseIcon /></IconButton></Box>
      {children}
    </Popover>
  </>;
}
