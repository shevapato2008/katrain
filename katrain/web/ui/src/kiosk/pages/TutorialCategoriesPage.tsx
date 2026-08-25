import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { TutorialReadAPI } from '../../api/tutorialApi';
import { useTranslation } from '../../hooks/useTranslation';
import type { TutorialCategory } from '../../types/tutorial';
import { KioskCard } from '../shell/KioskCard';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 23 · 课程 `/kiosk/tutorial` —— L1 布局 A(镜像栏 296 + 16 + 右栏 680),形态 1(整栏滚)。
 *
 * 后端是**分类 → 书 → 章 → 节 → 图**五层,还带旁白音频,**内容不在这台盒子上生成**。
 * 这一屏只管最外那层:列分类,点进去是书目。
 *
 * ## 环里写「—」还是写数,判据是「查过了没有」
 *
 * 稿子那三张卡的环里是「—」,理由稿子写死了:**`0` 意味着「查过了,一本都没有」,
 * 而稿子那张图画的是一台还没跟云端对过账的盒子** ——「同步不到」和「一本都没有」
 * 是两种状态,得分开报。
 *
 * ⚠️ 但这里的环**不是本数,是进度**(`KioskCard` 的 `ring` 渲染成 `NN%`)。
 * 每一类看到哪儿了,`/api/v1/tutorials/categories` 不给 —— 它只给 `book_count`。
 * ⇒ 环恒为 `null`(屏上是「—」),**本数落在卡的副标和组标题右端**,那两处是真数。
 * 拿本数去画进度环会画出一条谁也读不懂的弧。
 *
 * ## 分类名一个都不写死
 *
 * 稿子上那三个名字(入门 / 基本功 / 布局与定式)是**形状不是清单**。
 * 现状这一页就是读接口的,本轮保住这个行为。接口返回空 = 空态一句话,
 * **不摆一排点不开的卡让人以为快了**。
 *
 * ## 「现在能练的」只在没课的时候出现
 *
 * 一本课都没有的时候,这一屏的正事是**把人送到有内容的地方去**。
 * 有课的时候它就成了一排永远在的杂物 —— 所以只在分类为空时渲染。
 *
 * ## 和稿子不一样的两处
 *
 * ① 组标题右端稿子写「每类几本，由接口返回」——那是**说给读稿人听的**,
 *    而那一格的位置按规范放的是**数据**。改成真数:「N 类 · 共 M 本」。
 * ② 左栏那块盘稿子画了几颗示意子(「课上的图会摆到盘上」的意思)。
 *    实现照旧是**压暗的空盘** —— 那一栏是实体盘镜像,摆一盘不是这一局的子
 *    就是拿装饰冒充状态(D11)。同步行那句话已经把意思说清楚了。
 */
const TutorialCategoriesPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [categories, setCategories] = useState<TutorialCategory[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const loadCategories = useCallback(() => {
    let cancelled = false;
    // ⚠️ 清空只能在异步回调里(`react-hooks/set-state-in-effect`);重试那一下靠 `reload`
    // 计数器再进一次 —— `setError(null)` 写在这儿会在渲染期间改状态。
    TutorialReadAPI.getCategories()
      .then((data) => {
        if (cancelled) return;
        setCategories(data);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setCategories(null);
        setError(err instanceof Error ? err.message : String(err));
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => loadCategories(), [loadCategories, reload]);

  const sorted = useMemo(
    () => (categories ? [...categories].sort((a, b) => a.order - b.order) : null),
    [categories],
  );
  const books = sorted?.reduce((n, c) => n + (c.book_count || 0), 0) ?? 0;

  return (
    <KioskScrollZone resetKey={reload}>
      <div className="kiosk-greet">
        <b>{t('tutorial:title_cn', '课程')}<i>{t('tutorial:synced', '随云端同步')}</i></b>
        <span>{t('tutorial:greet_sub', '后端是五层结构，内容不在这台盒子上生成')}</span>
      </div>

      <section className="kiosk-section">
        <KioskSecLabel
          zh={t('tutorial:categories_cn', '分类')}
          en="Categories"
          // 稿子这一格写的是「每类几本，由接口返回」—— 那是说给读稿人听的。
          // 规范里这一格放的是**数据**,所以换成真数;还没读到就什么都不写。
          value={sorted
            ? interpolate(t('tutorial:count_line', '{n} 类 · 共 {b} 本'), { n: sorted.length, b: books })
            : undefined}
        />
        {error ? (
          <div className="empty" data-testid="tutorial-error">
            <h4>{t('tutorial:loadFailed', '加载失败，请稍后重试')}</h4>
            <p>{error}</p>
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill pill"
              onClick={() => { setError(null); setReload((v) => v + 1); }}
            >
              {t('kifu:retry', '重试')}
            </button>
          </div>
        ) : sorted == null ? (
          <div className="empty" data-testid="tutorial-loading">
            <h4>{t('tutorial:loading_cn', '正在跟云端对课')}</h4>
          </div>
        ) : books === 0 ? (
          /**
           * ⚠️ **判别位是 `books`,不是 `sorted.length`**(2026-08-25,S1)。
           *
           * 分类是**写死的四条**(`katrain/web/tutorials/db_queries.py:22-27` 的
           * `CATEGORIES`,`get_categories()` 无条件原样返回)⇒ 这条接口永远回 4 行,
           * `sorted.length === 0` **经真后端一次都走不到**:一本课都没有的时候,
           * 屏上会摆出四张「0 本」的卡,而这个空态分支永远不显示。
           *
           * 「答了、答的是空」这个判断本身没错,错的是**空在哪一层**:
           * 空的是书,不是分类。
           */
          <div className="empty" data-testid="tutorial-empty">
            <h4>{t('tutorial:empty', '暂无教程')}</h4>
            {/* 不写「同步」—— 盒子上 tutorials 是**实时代理**(`board.py` 的
                `proxy_tutorial_categories` → `remote_client.get_tutorial_categories`),
                全仓没有任何同步机制。说「还没同步下来」会让人以为等一会儿就有。 */}
            <p>{t('tutorial:empty_hint', '云端的课程库里还没有书；下面两处现在就有内容。')}</p>
          </div>
        ) : (
          <div className="kiosk-cards" data-testid="tutorial-categories">
            {sorted.map((cat) => (
              <KioskCard
                key={cat.slug}
                title={cat.title}
                // 本数是真数,进度不是 —— 所以本数写在这儿,环里恒是「—」。
                sub={[cat.summary, interpolate(t('tutorial:books_n', '{n} 本'), { n: cat.book_count })]
                  .filter(Boolean).join(' · ')}
                ring={null}
                onClick={() => navigate(`/kiosk/tutorial/${cat.slug}`)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="kiosk-section">
        <KioskSecLabel zh={t('tutorial:anatomy_cn', '一课长什么样')} en="Anatomy" />
        <div className="kiosk-rows" data-testid="tutorial-anatomy">
          {([
            ['book', '书', '一本书', '分若干章', 'Book', false],
            ['chapter', '章', '一章讲一块', '比如「吃子」是一章', 'Chapter', false],
            ['section', '节', '节才是「一课」', '翻完一节的图就算看完', 'Section', false],
            ['figure', '图', '节里是一张张棋图', '每张图带一段人声旁白，还能一键摆到实体盘上', '带音频', true],
          ] as const).map(([key, lead, title, sub, tag, good]) => (
            <div className="kiosk-row" key={key}>
              <span className="kiosk-row__lead">{t(`tutorial:layer_${key}_lead`, lead)}</span>
              <span className="kiosk-row__t">
                <b>{t(`tutorial:layer_${key}_t`, title)}</b>
                <em>{t(`tutorial:layer_${key}_s`, sub)}</em>
              </span>
              <span className="kiosk-row__end">
                <span className={good ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag'}>
                  {good ? t('tutorial:layer_audio', tag) : tag}
                </span>
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* 一本课都没有的时候,这一屏的正事是把人送到有内容的地方去。
          有课的时候它就成了一排永远在的杂物 —— 所以只在分类为空时渲染。 */}
      {sorted != null && books === 0 && (
        <section className="kiosk-section">
          <KioskSecLabel zh={t('tutorial:instead_cn', '现在能练的')} en="Instead" />
          <div className="kiosk-cards" data-testid="tutorial-instead">
            <KioskCard
              title={t('tutorial:go_training', '去训练营')}
              sub={t('tutorial:go_training_sub', '六类题 · 现在就能做')}
              icon="puzzle-piece"
              onClick={() => navigate('/kiosk/tsumego')}
            />
            <KioskCard
              title={t('tutorial:go_baipu', '去摆谱')}
              sub={t('tutorial:go_baipu_sub', '跟着名局摆一遍')}
              icon="grid-nine"
              onClick={() => navigate('/kiosk/baipu')}
            />
          </div>
        </section>
      )}
    </KioskScrollZone>
  );
};

export default TutorialCategoriesPage;
