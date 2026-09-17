import { Box, Button, LinearProgress, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

interface BoardSetupGuideProps {
  matched: number;
  total: number;
  missing: Array<[number, number]>; // [row, col] positions
  extra?: Array<[number, number, number]>;
  stage?: 'black' | 'white' | null;
  onSkip: () => void;
}

/**
 * 实体做题「摆题中」那一段的引导。只有做题屏一个调用方(`TsumegoProblemPage`)。
 *
 * 2026-09-14(T8):**删掉「开始答题」键**。调用方写死 `isComplete={false}` 和空回调,
 * 而状态机一摆好就自动进答题(`physicalTsumegoMachine.ts` 的 `toReady`)、这块引导随之消失 ——
 * 那颗键在它可见的整个期间都按不动,右栏一直挂着一颗死键。
 * 「跳过设置」保留:它等于关掉实体模式,人在摆盘时想放弃,出口就该在眼前。
 *
 * 皮肤没换(仍是 7 月的 MUI):稿子没画实体摆题这一态,重画与上板走查一起做(prd.md §5)。
 */
const BoardSetupGuide = ({ matched, total, missing: _missing, extra = [], stage = null, onSkip }: BoardSetupGuideProps) => {
  const { t } = useTranslation();
  const progress = total > 0 ? (matched / total) * 100 : 0;
  const matchedText = interpolate(t('tsumego:setupMatched', '已匹配 {matched}/{total} 颗子'), { matched, total });
  const stageText =
    stage === 'black'
      ? t('tsumego:setupStageBlack', '请摆放黑棋')
      : stage === 'white'
        ? t('tsumego:setupStageWhite', '请摆放白棋')
        : null;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        p: 2,
        bgcolor: 'background.paper',
        borderRadius: 2,
        border: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="body1" sx={{ fontWeight: 500 }}>
        {stageText ? `${stageText} · ${matchedText}` : matchedText}
      </Typography>
      {extra.length > 0 && (
        <Typography variant="body2" color="warning.main">
          {interpolate(
            t('tsumego:setupExtra', '盘上有 {n} 颗多余/错色棋子，请先取走（屏上红叉 ✕ 标注，实体棋盘白灯闪烁）'),
            { n: extra.length },
          )}
        </Typography>
      )}

      <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 1 }} />

      <Box sx={{ display: 'flex', gap: 1.5, mt: 0.5 }}>
        <Button variant="outlined" size="medium" onClick={onSkip} sx={{ flex: 1 }}>
          {t('tsumego:setupSkip', '跳过设置')}
        </Button>
      </Box>
    </Box>
  );
};

export default BoardSetupGuide;
