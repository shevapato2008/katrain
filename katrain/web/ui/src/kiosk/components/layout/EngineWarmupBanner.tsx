import { useEngineReadiness } from '../../context/EngineReadinessContext';
import { useTranslation } from '../../../hooks/useTranslation';

const EngineWarmupBanner = () => {
  const readiness = useEngineReadiness();
  const { t } = useTranslation();
  if (readiness === 'ready') return null;

  // ⚠️ 韩文等界面之前显示的是硬编码中文 —— 没走 t(),i18n 闸对这一类完全失明
  // (它从 t('key','中文') 调用里抽 key,从没出现在 t() 里的字符串它根本看不见)。
  const message = readiness === 'warming'
    ? t('engine:warmup_warming', 'AI 引擎准备中，可先使用棋谱、课程等功能')
    : t('engine:warmup_unavailable', 'AI 引擎暂未就绪，可稍后重试');

  return (
    <div
      className={`kiosk-engine-warmup is-${readiness}`}
      role="status"
      aria-live="polite"
    >
      {message}
    </div>
  );
};

export default EngineWarmupBanner;
