import { Fragment, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { categoryRank, isDanLevel, levelChinese, loadErrorCopy, readLastLevel, readPracticeResume } from './tsumegoUnits';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

/**
 * 屏 11 · 训练营 `/kiosk/tsumego` —— L1 布局 A(镜像栏 296 + 16 + 右栏 680)。
 * 稿子 `sample-go/go-kiosk.tmpl.html` 的 `data-screen="training"`,参考图 `shots/11-training.png`。
 *
 * Galaxy 同一条主路径:先按难度选一档,下一屏再选题型,然后才进单元。
 * 左栏镜像仍由 `KioskLayout` 渲染;右栏只承担问候、继续训练和连续难度阶梯。
 *
 * ── 三条口径,都是「不许编」的具体落法 ──────────────────────────────────
 *
 * `/levels` 已按由易到难返回真实 22 档(以题库为准)。每行的彩条只表示这一档各题型的题量构成;
 * 它不是完成进度,因此不再画会被误读成进度的「—」圆环。
 */
const TsumegoPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [levels, setLevels] = useState<LevelInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resume = readPracticeResume();
  const lastLevel = readLastLevel();

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

  // 问候行是**一条**可翻译的句子,重点词用 `{what}` 占位标出来 —— 照现有的 `{n}` 惯例
  // (`'数子要下满 {n} 手'`)。拆成两个 msgid 会让译者看不到整句,而中英之间该不该有空格
  // 恰恰在整句里才定得下来(中文没有,英文有)。
  const [greetHead, greetTail] = t('Today we practice {what}', '今天练点{what}').split('{what}');
  const greet = (
    <div className="kiosk-greet">
      <b>{greetHead}<i>{t('what', '什么')}</i>{greetTail}</b>
      {/* 稿子写「题在实体盘上摆好，落子即判」—— 实体做题开关默认关,无摄像头的盒子根本没有实体盘,
          那句只在一种情况下成立(N26③)。换成屏幕 / 实体盘 / 有无摄像头都成立的一句。 */}
      <span>{t('tsumego:greetSub', '落子即判，走错当场退回')}</span>
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
  if (levels === null || error || levels.length === 0) {
    return (
      <KioskScrollZone>
        {greet}
        {resumeBar}
        {error ? (
          <div className="empty" data-testid="tsumego-error">
            <h4>{loadErrorCopy(t, error).title}</h4>
            <p>{loadErrorCopy(t, error).body}</p>
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
            {/* 接口真回了空。**不说「随云端同步下来」**:盒上题库是在线直读的,没有同步这回事(N9)。 */}
            <h4>{t('tsumego:bankEmpty', '题库里还没有题')}</h4>
          </div>
        )}
      </KioskScrollZone>
    );
  }

  const span = levels.length > 1
    ? `${levelChinese(levels[0].level)} → ${levelChinese(levels[levels.length - 1].level)} · ${levels.length} ${t('tsumego:levelsUnit', '档')}`
    : levelChinese(levels[0].level);

  return (
    <KioskScrollZone>
      {greet}
      {resumeBar}

      <section className="kiosk-section">
        <KioskSecLabel zh={t('tsumego:chooseByLevel', '按棋力选择')} en={'Choose\u00a0level'} value={span} />
        <div className="tsumego-level-list">
          {levels.map((level, index) => {
            const current = level.level === lastLevel;
            const categories = Object.entries(level.categories)
              .sort(([a], [b]) => categoryRank(a) - categoryRank(b) || a.localeCompare(b));
            const beginsDan = isDanLevel(level.level) && index > 0 && !isDanLevel(levels[index - 1].level);
            return (
              <Fragment key={level.level}>
                {beginsDan ? (
                  <div className="tsumego-level-seam" aria-label={t('tsumego:rankBoundary', '级位与段位分界')}>
                    <span>{t('tsumego:kyuRanks', '级位')}</span><b>1K → 1D</b><span>{t('tsumego:danRanks', '段位')}</span>
                  </div>
                ) : null}
                <button
                  type="button"
                  className={`tsumego-level-row${current ? ' is-current' : ''}`}
                  aria-label={[
                    levelChinese(level.level),
                    `${level.total} ${t('tsumego:problems', '题')}`,
                    current ? t('tsumego:yourLevel', '你的水平') : undefined,
                  ].filter(Boolean).join('，')}
                  onClick={() => navigate(`/kiosk/tsumego/${level.level}`)}
                >
                  <b>{levelChinese(level.level)}</b>
                  <span className={`tsumego-level-row__tag${current ? ' is-current' : ''}`}>
                    {current ? t('tsumego:yourLevel', '你的水平') : t('tsumego:specializedPractice', '专项训练')}
                  </span>
                  <span className="tsumego-level-row__mix" aria-label={`${categories.length} ${t('tsumego:category_unit', '类')}`}>
                    {categories.map(([key, count], categoryIndex) => (
                      <i key={key} className={`tone-${categoryIndex % 6}`} style={{ flexGrow: count }} />
                    ))}
                  </span>
                  <span className="tsumego-level-row__count">{level.total} {t('tsumego:problems', '题')}</span>
                  <span className="tsumego-level-row__arrow" aria-hidden="true">›</span>
                </button>
              </Fragment>
            );
          })}
        </div>
      </section>
    </KioskScrollZone>
  );
};

export default TsumegoPage;
