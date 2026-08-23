/* 死活题 · 难度列表 —— 冻结原型 `tsumego-levels` 的改版态（「不接进度」那一支）。
 *
 * 稿子那段注解论证的是**结构**，不是那八行具体数据：
 *   现状 22 张等价方块之所以显得空，不是留白多，是**每张卡只有一个数字在承担全部信息**；
 *   而这一页真正的结构被抹掉了 —— 15K→7D 是**有序的**，`1K→1D` 是围棋里唯一那道坎。
 * 改法：用**行**不用**格**；级别数字降进徽章（它是标识不是标题），空出来的横向位置
 * 交给真信息（分布条 + 题数）；那道坎画成真的分隔。
 *
 * **稿子画的 8 档是虚构数据，真实接口回的是 22 档、7 个类目。**
 * `/api/v1/tsumego/levels` 实测：15k…1k 十五档 + 1d…7d 七档 = 22；类目有
 * life-death / tesuji / semeai / capturing / endgame / opening / midgame 七种，
 * 不是稿子画的三种。于是三处按真实数据落，不按稿子：
 *   1. **22 行，会滚**。稿子写「八行加上那道坎，正好一屏装下，不用滚」—— 那是按它自己
 *      虚构的 8 档说的。22 行在 1440x900 下装不完，滚就是了；这一页在自然流里，
 *      不引入任何新的裁切边界。
 *   2. **分布条按真实类目渲染**（每档实际出现几类就画几段），不硬收成三段。
 *      稿子「24 枚 chip 收成分布条」那个论证在 7 类下同样成立、而且更强
 *      （现状 22 档合计画了约 90 枚 chip）。
 *   3. **不写每档的名字和说明**（入门/初级/…及其解说）。那八个名字是挂在虚构的八档上的，
 *      22 档摊不下来；硬凑一份比没有更坏。「哪一档适合我」改由**你的水平**那个标记回答
 *      —— 稿子本来就有这个标记，而且它比八个档位名更直接。
 */
import { useState, useEffect, useMemo } from 'react';
import { Box, Typography, CircularProgress, Alert, ButtonBase } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useNavigate } from 'react-router-dom';
import { useSettings } from '../../context/SettingsContext';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import ContentPageHeader from '../components/layout/ContentPageHeader';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

/* 类目配色。第三段起用的是棋盘木色系，不另起一套配色（稿子同址）。
   顺序固定：分布条的段序在所有行里必须一致，否则「比例一眼可比」不成立。 */
const CATEGORY_ORDER = ['life-death', 'tesuji', 'semeai', 'capturing', 'endgame', 'opening', 'midgame'] as const;
const CATEGORY_COLOR: Record<string, string> = {
  'life-death': '#5d8270',
  tesuji: '#5b9bd5',
  semeai: '#b07d5a',
  capturing: '#8a7f6d',
  endgame: '#9a8fb0',
  opening: '#6f8fa3',
  midgame: '#a0705f',
};

/** `15k` → 15（级位，数字越小越强）；`3d` → 3（段位）。用来排序和分节。 */
const parseLevel = (level: string) => {
  const isDan = level.toLowerCase().endsWith('d');
  const value = parseInt(level, 10) || 0;
  return { isDan, value };
};

const TsumegoLevelsPage = () => {
  const navigate = useNavigate();
  useSettings(); // Subscribe to settings changes
  const { t } = useTranslation();
  const { user } = useAuth();
  const [levels, setLevels] = useState<LevelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/v1/tsumego/levels')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setLevels(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load levels:', err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  /* 排成一条真的阶梯：级位从弱到强（15K→1K），然后段位从弱到强（1D→7D）。
     接口回的顺序碰巧就是这个，但**不能靠碰巧** —— 排序写在这里，接口换了顺序也不会乱。 */
  const { kyuLevels, danLevels, maxTotal } = useMemo(() => {
    const kyu = levels.filter((l) => !parseLevel(l.level).isDan)
      .sort((a, b) => parseLevel(b.level).value - parseLevel(a.level).value);
    const dan = levels.filter((l) => parseLevel(l.level).isDan)
      .sort((a, b) => parseLevel(a.level).value - parseLevel(b.level).value);
    return { kyuLevels: kyu, danLevels: dan, maxTotal: Math.max(1, ...levels.map((l) => l.total)) };
  }, [levels]);

  /** 用户自己的水平。`fan` 这类没设过段位的账号 rank 是空的，那就一行都不高亮。 */
  const myLevel = (user?.rank || '').toLowerCase();

  /* 出现过的类目（按固定顺序），用来画图例。只画真的出现过的，
     免得图例上挂着一堆本库里根本没有的类目。 */
  const presentCategories = useMemo(() => CATEGORY_ORDER.filter(
    (cat) => levels.some((l) => (l.categories[cat] || 0) > 0),
  ), [levels]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
        <Alert severity="error">
          {t('tsumego:loadError', '死活题库加载失败，请稍后重试。')}
        </Alert>
      </Box>
    );
  }

  if (levels.length === 0) {
    return (
      <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
        <ContentPageHeader title={t('Tsumego')} />
        <Alert severity="info" sx={{ mt: 2 }}>
          {t('tsumego:noData', '暂无死活题。')}
        </Alert>
      </Box>
    );
  }

  const renderRung = (level: LevelInfo) => {
    const { isDan } = parseLevel(level.level);
    const isMine = level.level.toLowerCase() === myLevel;
    const segments = CATEGORY_ORDER
      .map((cat) => ({ cat, count: level.categories[cat] || 0 }))
      .filter((s) => s.count > 0);
    /* 无障碍名把整行读全：级别、题数、以及分布条里每一类各多少题。
       颜色不是唯一线索 —— 条上挂 `role="img"` + 完整 aria-label，读屏听得到。 */
    const barLabel = segments.map((s) => `${t(`tsumego:${s.cat}`)} ${s.count}`).join('、');
    const rowLabel = `${level.level.toUpperCase()}，${level.total} ${t('tsumego:problems', '题')}`
      + (isMine ? `，${t('tsumego:your_level', '你的水平')}` : '');

    return (
      <ButtonBase
        key={level.level}
        data-testid="tsumego-rung"
        aria-label={rowLabel}
        onClick={() => navigate(`/galaxy/tsumego/${level.level}`)}
        sx={{
          width: '100%',
          display: 'grid',
          /* 徽章 / 分布条（可伸缩，唯一吃掉剩余宽度的一列）/「你的水平」/ 题数 / 箭头。
             430 档去掉分布条那一列 —— 288 宽里画七段条只剩噪声。
             「你的水平」那一列**每行都占位**（不是自己那行才有）：宽度恒定，
             各行的分布条容器才等宽，「比例一眼可比」才成立。 */
          gridTemplateColumns: { xs: '52px 1fr 20px', sm: '52px minmax(0, 1fr) 68px 96px 20px' },
          alignItems: 'center',
          gap: { xs: 1.5, sm: 2 },
          px: { xs: 1.5, sm: 2 },
          py: 1.25,
          borderRadius: 2.5,
          textAlign: 'left',
          bgcolor: isDan ? 'rgba(255,255,255,0.035)' : 'rgba(255,255,255,0.02)',
          border: '1px solid',
          borderColor: isMine ? 'primary.main' : 'rgba(255,255,255,0.06)',
          borderLeftWidth: isMine ? 3 : 1,
          transition: 'background-color 160ms ease, border-color 160ms ease',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.14)' },
        }}
      >
        {/* 级别数字是**标识**不是标题：34px 徽章里 1.05rem，不是现状那个 3rem 的大字。 */}
        <Box
          sx={{
            height: 34, minWidth: 52, px: 1,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 1.5, fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.01em',
            bgcolor: isMine ? 'primary.main' : 'rgba(255,255,255,0.06)',
            color: isMine ? '#0f1512' : 'text.primary',
          }}
        >
          {level.level.toUpperCase()}
        </Box>

        <Box sx={{ minWidth: 0 }}>
          <Box
            role="img"
            aria-label={barLabel}
            sx={{
              display: { xs: 'none', sm: 'flex' },
              height: 8, borderRadius: 4, overflow: 'hidden',
              /* 条长按题数占最长那一档的比例，但保底 38% —— 全长条之间的差别才是
                 「这一档题多不多」，压到极短就只剩噪声了（稿子同一条式子）。 */
              width: `${(38 + (level.total / maxTotal) * 62).toFixed(1)}%`,
              minWidth: 120,
            }}
          >
            {segments.map((s) => (
              <Box
                key={s.cat}
                sx={{ width: `${((s.count / level.total) * 100).toFixed(2)}%`, bgcolor: CATEGORY_COLOR[s.cat] }}
              />
            ))}
          </Box>
          {/* 430 档没有分布条，那一列改放题数 —— 不然窄屏上只剩一个徽章和一个箭头。 */}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ display: { xs: 'block', sm: 'none' }, fontSize: '0.82rem' }}
          >
            {level.total} {t('tsumego:problems', '题')}
            {isMine && ` · ${t('tsumego:your_level', '你的水平')}`}
          </Typography>
        </Box>

        {/* 自己那一档要有**文字**，不能只靠玉色边和点亮的徽章 —— 稿子三条细节里
            第二条就是「颜色不是唯一线索」。窄档这句话并进上面那行题数里。

            不是自己那档时渲染一个**空占位**，不是把同样的文字设成 `visibility:hidden`：
            列宽本来就由 grid 轨道（68px）定死，用不着靠文字撑；而藏起来的文字仍然在
            DOM 里，谁按文本去找都会在 22 行上各找到一个。 */}
        {isMine ? (
          <Typography
            variant="caption"
            sx={{
              display: { xs: 'none', sm: 'block' },
              color: 'primary.light',
              fontSize: '0.68rem',
              letterSpacing: '0.06em',
              whiteSpace: 'nowrap',
            }}
          >
            {t('tsumego:your_level', '你的水平')}
          </Typography>
        ) : (
          <span aria-hidden="true" />
        )}

        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ display: { xs: 'none', sm: 'block' }, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}
        >
          {level.total} {t('tsumego:problems', '题')}
        </Typography>

        <ChevronRightIcon sx={{ fontSize: 20, color: 'text.secondary', opacity: 0.5 }} />
      </ButtonBase>
    );
  };

  const seam = (label: string) => (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 2.5, mb: 1 }}>
      <Typography variant="overline" sx={{ letterSpacing: '0.12em', color: 'text.secondary', lineHeight: 1 }}>
        {label}
      </Typography>
      <Typography variant="caption" sx={{ color: 'text.secondary', opacity: 0.6 }}>
        {t('tsumego:stronger_downward', '越往下越强')}
      </Typography>
      <Box sx={{ flex: 1, height: '1px', bgcolor: 'rgba(255,255,255,0.08)' }} />
    </Box>
  );

  return (
    /* `width:'100%'` 不能省。`galaxy-main` 是 `display:flex; flexDirection:column`，
       在 flex 容器里 `mx:'auto'`（cross 轴 margin auto）会把这一项**压成内容宽**、
       而不是先铺满再居中 —— 实测行宽只有 489px，右边 400 多像素空着。
       旧版是 Grid，卡片自己按百分比撑开所以看不出来；换成按内容定宽的行以后就露了。 */
    <Box sx={{ p: 4, width: '100%', maxWidth: 960, mx: 'auto', boxSizing: 'border-box' }}>
      <ContentPageHeader title={t('Tsumego')} />
      {/* 引导语原来是页头第二行，spec §2.4 禁长副标题进页头，下沉到正文首行。 */}
      <Typography variant="subtitle1" color="text.secondary" sx={{ mt: 1 }}>
        {t('tsumego:selectLevel')}
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1.25, mt: 2.5 }}>
        <Typography variant="overline" sx={{ letterSpacing: '0.12em', color: 'text.secondary' }}>
          {t('tsumego:all_levels', '全部难度 · {count} 档').replace('{count}', String(levels.length))}
        </Typography>
        {/* 图例只在顶部出现一次 —— 现状是每张卡上重复一遍类目名，22 张卡约 90 枚 chip。 */}
        <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          {presentCategories.map((cat) => (
            <Box key={cat} sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
              <Box sx={{ width: 9, height: 9, borderRadius: 0.5, bgcolor: CATEGORY_COLOR[cat] }} />
              <Typography variant="caption" color="text.secondary">{t(`tsumego:${cat}`)}</Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {kyuLevels.length > 0 && (
        <>
          {seam(t('tsumego:kyu_tier', '级位'))}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {kyuLevels.map(renderRung)}
          </Box>
        </>
      )}

      {danLevels.length > 0 && (
        <>
          {/* 唯一那道坎：`1K → 1D`。段位那一节整体换一档略亮的底色（见 `renderRung`）。 */}
          {seam(t('tsumego:dan_tier', '段位'))}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {danLevels.map(renderRung)}
          </Box>
        </>
      )}
    </Box>
  );
};

export default TsumegoLevelsPage;
