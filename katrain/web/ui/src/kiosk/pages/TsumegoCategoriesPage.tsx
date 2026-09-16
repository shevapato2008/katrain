import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import { useTranslation } from '../../hooks/useTranslation';
import { KioskCard } from '../shell/KioskCard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import {
  CATEGORY_META,
  categoryRank,
  levelChinese,
  loadErrorCopy,
  readLastCategory,
} from './tsumegoUnits';

interface CategoryInfo {
  category: string;
  name: string;
  count: number;
}

interface ProblemSummary {
  id: string;
}

/**
 * Route: tsumego/:level — category selection after choosing a difficulty.
 *
 * The category counts arrive first. Per-category ID lists load in parallel so
 * completion totals can appear without blocking the page.
 */
const TsumegoCategoriesPage = () => {
  const { level } = useParams<{ level: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { categoryProgress } = useTsumegoProgress();

  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [categoryIds, setCategoryIds] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCategories = useCallback((lvl: string, signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    setCategoryIds({});

    fetch(`/api/v1/tsumego/levels/${lvl}/categories`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: CategoryInfo[]) => {
        setCategories(data);
        setLoading(false);

        data.forEach((cat) => {
          fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat.category}?limit=1000`, { signal })
            .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
            .then((problems: ProblemSummary[]) => {
              if (Array.isArray(problems)) {
                setCategoryIds((prev) => ({ ...prev, [cat.category]: problems.map((problem) => problem.id) }));
              }
            })
            .catch(() => {
              // Completion is best-effort; the category itself stays available.
            });
        });
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    if (!level) return;
    const controller = new AbortController();
    loadCategories(level, controller.signal);
    return () => controller.abort();
  }, [level, loadCategories]);

  const orderedCategories = useMemo(
    () => [...categories].sort((a, b) => categoryRank(a.category) - categoryRank(b.category)
      || a.category.localeCompare(b.category)),
    [categories],
  );
  const totalCount = categories.reduce((sum, category) => sum + category.count, 0);
  const levelName = level ? levelChinese(level) : '';
  const lastCategory = readLastCategory();

  const pagebar = (
    <KioskPagebar
      title={`${levelName} · ${t('Select category', '选择题型')}`}
      sub={loading ? t('Loading…', '加载中…') : `${totalCount} 题 · ${categories.length} 类`}
      backLabel={t('Difficulty', '难度')}
      onBack={() => navigate('/kiosk/tsumego')}
    />
  );

  if (loading || error || categories.length === 0) {
    return (
      <div className="kiosk-layout-b">
        {pagebar}
        <KioskScrollZone>
          {loading ? (
            <div className="empty" data-testid="categories-loading">
              <h4>{t('Loading categories…', '正在读取题型…')}</h4>
            </div>
          ) : error ? (
            <div className="empty" data-testid="categories-error">
              <h4>{loadErrorCopy(t, error).title}</h4>
              <p>{loadErrorCopy(t, error).body}</p>
              <div className="tsumego-empty-actions">
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--pill pill"
                  onClick={() => {
                    if (level) loadCategories(level, new AbortController().signal);
                  }}
                >
                  {t('Retry', '重试')}
                </button>
              </div>
            </div>
          ) : (
            <div className="empty" data-testid="categories-empty">
              <h4>{t('No categories at this level yet', '这一档下面还没有题型')}</h4>
            </div>
          )}
        </KioskScrollZone>
      </div>
    );
  }

  return (
    <div className="kiosk-layout-b">
      {pagebar}
      <KioskScrollZone resetKey={level}>
        <section className="kiosk-section">
          <KioskSecLabel zh={t('Focused training', '专项训练')} en="Categories" value={t('Choose one category', '选择一个题型')} />
          <div className="tsumego-category-grid">
            {orderedCategories.map((category) => {
              const meta = CATEGORY_META[category.category];
              const ids = categoryIds[category.category];
              const summary = ids ? categoryProgress(ids) : null;
              const categoryName = t(`tsumego:${category.category}`, meta?.zh ?? category.name);
              return (
                <KioskCard
                  key={category.category}
                  title={categoryName}
                  sub={summary ? `${summary.completed} / ${summary.total} 题` : `${category.count} 题`}
                  icon={meta?.icon ?? 'puzzle-piece'}
                  current={lastCategory === category.category}
                  onClick={() => navigate(`/kiosk/tsumego/${level}/${category.category}`)}
                />
              );
            })}
          </div>
        </section>

        <section className="kiosk-section tsumego-mixed-section">
          <KioskSecLabel zh={t('Mixed categories', '混合题型')} en="Mixed" value={`${totalCount} 题`} />
          <div className="tsumego-mixed-card">
            <KioskCard
              title={t('Mixed training', '综合训练')}
              sub={t('Mix all categories at this level and group every 20 problems into a unit', '混合当前难度全部题型，也按每 20 题分成单元')}
              icon="squares-four"
              current={lastCategory === 'all'}
              ariaLabel={`${t('Mixed training', '综合训练')}，${totalCount} 题，${t('20 problems per unit', '每 20 题一单元')}`}
              onClick={() => navigate(`/kiosk/tsumego/${level}/all`)}
            />
          </div>
        </section>
      </KioskScrollZone>
    </div>
  );
};

export default TsumegoCategoriesPage;
