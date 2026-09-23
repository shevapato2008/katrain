import { useEngineReadiness } from '../../context/EngineReadinessContext';

const EngineWarmupBanner = () => {
  const readiness = useEngineReadiness();
  if (readiness === 'ready') return null;

  const message = readiness === 'warming'
    ? 'AI 引擎准备中，可先使用棋谱、课程等功能'
    : 'AI 引擎暂未就绪，可稍后重试';

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
