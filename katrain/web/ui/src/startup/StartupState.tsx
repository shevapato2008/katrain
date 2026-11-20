import { useTranslation } from '../hooks/useTranslation';
import './startup.css';

export function StartupLoading() {
  const { t } = useTranslation();
  return <div className="startup-state" role="status">{t('startup:loading', '正在加载…')}</div>;
}

export function StartupFailure({ category, onRetry }: {
  category: 'render' | 'preload';
  onRetry: () => void;
}) {
  const { t } = useTranslation();
  return (
    <section className={category === 'render' ? 'startup-state' : 'startup-preload-notice'} role="alert">
      <p>{category === 'render'
        ? t('startup:render_error', '页面暂时无法显示')
        : t('startup:preload_error', '部分页面加载失败')}</p>
      <button className="startup-retry" type="button" onClick={onRetry}>
        {t('startup:reload', '重新加载')}
      </button>
    </section>
  );
}
