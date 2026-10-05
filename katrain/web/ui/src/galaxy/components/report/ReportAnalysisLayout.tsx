import { useState, type ReactNode } from 'react';
import { Box, Button } from '@mui/material';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import CloseFullscreenIcon from '@mui/icons-material/CloseFullscreen';
import { useTranslation } from '../../../hooks/useTranslation';

interface Props {
  identity: ReactNode;
  recommendations: ReactNode;
  analysis: ReactNode;
  controls: ReactNode;
  navigation: ReactNode;
}

/** The report-only rail: every primary area stays in place while moves and tabs change. */
export default function ReportAnalysisLayout({ identity, recommendations, analysis, controls, navigation }: Props) {
  const [expanded, setExpanded] = useState(false);
  const { t } = useTranslation();
  return <Box data-testid="report-analysis-layout" sx={{ height: '100%', minHeight: 0, display: 'grid', gridTemplateRows: '154px 250px minmax(0,1fr) 86px 58px', gap: 1, py: 1, boxSizing: 'border-box' }}>
    <Box sx={{ minHeight: 0, overflow: 'hidden' }}>{identity}</Box>
    <Box data-testid="report-recommendations" sx={{ minHeight: 0, overflowX: 'hidden', overflowY: 'auto', border: '1px solid', borderColor: 'divider', borderRadius: 1.5, bgcolor: 'background.paper' }}>{recommendations}</Box>
    {expanded && <Box onClick={() => setExpanded(false)} sx={{ position: 'fixed', inset: 0, bgcolor: '#000b', zIndex: 1299 }} />}
    <Box data-testid="report-analysis-tabs" sx={{ position: expanded ? 'fixed' : 'relative', ...(expanded ? { inset: '6vh 6vw', zIndex: 1300, boxShadow: 24 } : {}), minHeight: 0, overflow: expanded ? 'auto' : 'hidden', border: '1px solid', borderColor: 'divider', borderRadius: 1.5, bgcolor: 'background.paper', '& .MuiTypography-root, & .MuiTab-root': { fontSize: '18px !important' }, '& svg text': { fontSize: '18px !important' } }}>
      {analysis}
      <Button onClick={() => setExpanded((value) => !value)} aria-label={expanded ? t('report:collapse_analysis', '收起分析') : t('report:expand_analysis', '展开分析')} title={expanded ? t('report:collapse_analysis', '收起分析') : t('report:expand_analysis', '展开分析')} sx={{ position: 'absolute', right: 8, top: 4, zIndex: 2, minWidth: 36, width: 36, height: 36, p: 0, bgcolor: 'primary.dark', color: 'text.primary', '&:hover': { bgcolor: 'primary.main' } }}>{expanded ? <CloseFullscreenIcon fontSize="small" /> : <OpenInFullIcon fontSize="small" />}</Button>
    </Box>
    <Box sx={{ minHeight: 0 }}>
      <Box sx={{ minHeight: 0 }}>{controls}</Box>
    </Box>
    <Box sx={{ minHeight: 0 }}>{navigation}</Box>
  </Box>;
}
