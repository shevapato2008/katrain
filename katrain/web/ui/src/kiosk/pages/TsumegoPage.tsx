import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { readActiveSession } from '../utils/activeSession';
import { levelChinese, readLastCategory, readLastLevel } from './tsumegoUnits';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskCard } from '../shell/KioskCard';
import type { IconName } from '../shell/icons';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

/**
 * 题库自带的六个标签(`life-death / tesuji / semeai / capturing / endgame / opening`),
 * 从每道题的 SGF 注释里解析出来 —— **不是界面自己分的**。所以这张表只负责给它们配
 * 中文名、图标和一句话说明,**有哪几类由 `/levels` 说了算**:表里有、题库里没有的不画,
 * 题库里有、表里没有的照画(标题退回原始 key,副标写题量)。
 * 中文名与 cn PO 的 `tsumego:*` msgstr 一致,拿来当 `t()` 的兜底,翻译表没到位时也读得通。
 */
const CATEGORY_META: Record<string, { zh: string; sub: string; icon: IconName }> = {
  'life-death': { zh: '死活', sub: '做活 / 杀棋', icon: 'puzzle-piece' },
  tesuji: { zh: '手筋', sub: '局部那一手妙手', icon: 'hand-pointing' },
  semeai: { zh: '对杀', sub: '两块棋比气', icon: 'users' },
  capturing: { zh: '吃子', sub: '怎么把子吃下来', icon: 'grid-nine' },
  endgame: { zh: '官子', sub: '收官那几目', icon: 'squares-four' },
  opening: { zh: '布局', sub: '开局怎么占', icon: 'crown-simple' },
};

const CATEGORY_ORDER = Object.keys(CATEGORY_META);

/** 表里的排前面(照稿子那六张的顺序),表外的按 key 排在后面 —— 不让未知分类插队。 */
const categoryRank = (key: string) => {
  const i = CATEGORY_ORDER.indexOf(key);
  return i < 0 ? CATEGORY_ORDER.length : i;
};

/**
 * 屏 11 · 训练营 `/kiosk/tsumego` —— L1 布局 A(镜像栏 296 + 16 + 右栏 680)。
 * 稿子 `sample-go/go-kiosk.tmpl.html` 的 `data-screen="training"`,参考图 `shots/11-training.png`。
 *
 * 右栏四块:问候行 → 接着上次 → 按分类 → 按级别。左栏那条镜像栏由 `KioskLayout` 渲染。
 *
 * ── 三条口径,都是「不许编」的具体落法 ──────────────────────────────────
 *
 * ① **进度环里写「—」不写 0%**(G8)。题库(`data/life-n-death` 那批 SGF)**不在仓库里**,
 *    靠 `sync_tsumego_db.py` 灌进库、随云端更新;每一档做完没做完要按级把该级所有题号取回来
 *    才算得出,那是 R2/§3.5 当年明确不做的事(SBC 上一次取几千个 id 太贵)。
 *    ⇒ 环恒为 `null`。**这和单元列表屏的 `0%` 不是一回事**:那边的进度真存在
 *    `/api/v1/tsumego/progress` 里,`0%` 是「真的一道没做」;这边是「我不知道」。两屏的差别不许抹平。
 *
 * ② **一档有多少题、有哪几档,全从 `/levels` 来。** 稿子上画的是 15 级 / 10 级 / 5 级 / 1 级 /
 *    3 段 / 7 段 六张,那是**稿子挑的六个代表**;真实现照单全收后端返回的每一档,
 *    从易到难(`level_sort_key`:级越大越弱、段越大越强)。副标写题量 —— 稿子那句
 *    「最容易的一档 / 会吃子之后 / …」是逐档手写的,而档数是变的,写不出来也不该现编。
 *
 * ③ **「按分类」是有级别作用域的。** 路由是级别在前(`tsumego/:level/:category`),
 *    所以这一排卡必须先有一个级别 —— 取上次做题那一档(`readLastLevel`),没有就取最弱的那档。
 *    组标题右端的值写明是哪一档,不让人对着六张卡猜它们属于谁。
 */
const TsumegoPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [levels, setLevels] = useState<LevelInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resume = readActiveSession('practice');
  const lastLevel = readLastLevel();
  const lastCategory = readLastCategory();

  const load = useCallback(() => {
    setLevels(null);
    setError(null);
    fetch('/api/v1/tsumego/levels')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: LevelInfo[]) => setLevels(data))
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  // 作用域那一档:上次做的(且后端还有这一档)优先,否则最弱的那档 —— `/levels` 已按从易到难排好。
  const scoped = levels?.find(l => l.level === lastLevel) ?? levels?.[0] ?? null;

  // 问候行是**一条**可翻译的句子,重点词用 `{what}` 占位标出来 —— 照现有的 `{n}` 惯例
  // (`'数子要下满 {n} 手'`)。拆成两个 msgid 会让译者看不到整句,而中英之间该不该有空格
  // 恰恰在整句里才定得下来(中文没有,英文有)。
  const [greetHead, greetTail] = t('Today we practice {what}', '今天练点{what}').split('{what}');
  const greet = (
    <div className="kiosk-greet">
      <b>{greetHead}<i>{t('what', '什么')}</i>{greetTail}</b>
      <span>{t('Problems are set on the physical board · judged as you place', '题在实体盘上摆好，落子即判')}</span>
    </div>
  );

  const resumeBar = resume && (
    <div className="kiosk-resume" data-testid="tsumego-resume-card">
      <span className="bar" />
      <div>
        <h4>{t('Continue practicing', '接着上次')}</h4>
        <p>{resume.label}</p>
      </div>
      <button
        type="button"
        className="kiosk-btn kiosk-btn--pill pill"
        onClick={() => navigate(resume.route)}
      >
        {t('Continue', '继续')}
      </button>
    </div>
  );

  // 三态各说各的话,一态都不许冒充另一态,更不许冒充「加载完了、就是没有」。
  if (levels === null || error || levels.length === 0 || !scoped) {
    return (
      <KioskScrollZone>
        {greet}
        {resumeBar}
        {error ? (
          <div className="empty" data-testid="tsumego-error">
            <h4>{t('Problem set unavailable', '题库读不到')}</h4>
            <p>{error}</p>
            <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={load}>
              {t('Retry', '重试')}
            </button>
          </div>
        ) : levels === null ? (
          <div className="empty" data-testid="tsumego-loading">
            <h4>{t('Loading problem set…', '正在读题库…')}</h4>
          </div>
        ) : (
          <div className="empty" data-testid="tsumego-empty">
            <h4>{t('No problems on this box yet', '这台盒子上还没有题')}</h4>
            <p>{t('The problem set syncs down from the cloud.', '题库随云端同步下来，同步过来才有题可做。')}</p>
          </div>
        )}
      </KioskScrollZone>
    );
  }

  const categories = Object.entries(scoped.categories)
    .sort(([a], [b]) => categoryRank(a) - categoryRank(b) || a.localeCompare(b));
  const span = levels.length > 1
    ? `${levelChinese(levels[0].level)} → ${levelChinese(levels[levels.length - 1].level)}`
    : levelChinese(levels[0].level);

  return (
    <KioskScrollZone>
      {greet}
      {resumeBar}

      <section className="kiosk-section">
        <KioskSecLabel
          zh={t('By category', '按分类')}
          en={'By\u00a0category'}
          value={`${levelChinese(scoped.level)} · ${categories.length} ${t('tsumego:categories', '类')}`}
        />
        <div className="kiosk-cards">
          {categories.map(([key, count]) => {
            const meta = CATEGORY_META[key];
            return (
              <KioskCard
                key={key}
                title={t(`tsumego:${key}`, meta?.zh ?? key)}
                // 表外的分类没有手写说明,写题量 —— 那是这一格唯一知道为真的事。
                sub={meta ? meta.sub : `${count} ${t('tsumego:problems', '题')}`}
                icon={meta?.icon ?? 'puzzle-piece'}
                current={key === lastCategory}
                onClick={() => navigate(`/kiosk/tsumego/${scoped.level}/${key}`)}
              />
            );
          })}
        </div>
      </section>

      <section className="kiosk-section">
        <KioskSecLabel zh={t('By level', '按级别')} en={'By\u00a0level'} value={span} />
        <div className="kiosk-cards">
          {levels.map((level) => (
            <KioskCard
              key={level.level}
              // 环是「这一档做到哪了」,而这一层算不出(见文件头 ①)⇒ 恒 null,卡上写「—」。
              ring={null}
              title={levelChinese(level.level)}
              sub={`${level.total} ${t('tsumego:problems', '题')}`}
              current={level.level === lastLevel}
              ariaLabel={[
                levelChinese(level.level),
                `${level.total} ${t('tsumego:problems', '题')}`,
                t('progress unknown', '进度未知'),
              ].join('，')}
              onClick={() => navigate(`/kiosk/tsumego/${level.level}`)}
            />
          ))}
        </div>
      </section>
    </KioskScrollZone>
  );
};

export default TsumegoPage;
