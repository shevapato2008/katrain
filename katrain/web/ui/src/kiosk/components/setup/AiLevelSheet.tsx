import { useEffect, useRef } from 'react';
import type { EngineLevel } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

/**
 * 39 档全表 —— 名牌点开后覆盖在右栏上的一层。
 *
 * ## 为什么它不违反「一屏一种选择手势」
 *
 * 2026-08-24 那条裁定禁的是**两套选择控件同时摆在屏上**(轨 + 摊开的列表)。
 * 这一层点开即用、选完即关,任一时刻屏上只有一种手势。它解决的是轨解决不了的
 * 那件事:39 档每档约 8px,跨到远处只能长按连发。裁定文字已在 `tokens.css`
 * `.kiosk-optseg` 上方的规范注释里补了这条例外(2026-09-23)。
 *
 * ## 只盖右栏,不盖盘
 *
 * `position:absolute` 相对 `.kiosk-rail`,不是 `fixed` —— 左边那块盘画的是
 * 「按下开始之后会出现的局面」,盖住它就没了反馈。这也是当初撤掉 MUI Select 的理由。
 */
interface AiLevelSheetProps {
  levels: EngineLevel[];
  currentElo: number | null;
  onPick: (elo: number) => void;
  onClose: () => void;
  testId?: string;
}

const AiLevelSheet = ({ levels, currentElo, onPick, onClose, testId }: AiLevelSheetProps) => {
  const { t } = useTranslation();
  const currentRef = useRef<HTMLButtonElement>(null);

  // 打开时把当前那一档滚到可视区 —— 39 档里第 22 档在默认视口外。
  useEffect(() => { currentRef.current?.scrollIntoView({ block: 'center' }); }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="aisheet"
      data-testid={testId}
      role="dialog"
      aria-modal="true"
      aria-label={t('platform:level_sheet', '全部棋力档')}
    >
      <div className="aisheet__head">
        <b>{t('platform:level_sheet', '全部棋力档')}</b>
        <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={onClose}>
          {t('platform:close', '收起')}
        </button>
      </div>
      {levels.length === 0 ? (
        <p className="lobbyempty">{t('platform:levels_failed', '没能从平台取回棋力档')}</p>
      ) : (
        <div className="aisheet__body" data-scrollbar>
          {levels.map((l, i) => (
            <div className="aisheet__row" data-testid="level-row" key={l.elo_score}>
              <button
                type="button"
                ref={l.elo_score === currentElo ? currentRef : undefined}
                aria-current={l.elo_score === currentElo ? 'true' : undefined}
                onClick={() => { onPick(l.elo_score); onClose(); }}
              >
                <span className="idx">{i + 1}</span>
                <span className="nm">{l.name} · {l.level_name}</span>
                <span className="el">
                  {interpolate(t('platform:display_elo', '展示 Elo {v}'), { v: l.display_elo })}
                  {l.ref_rank ? ` · ${interpolate(t('platform:ref_rank', '对标{r}'), { r: l.ref_rank })}` : ''}
                </span>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AiLevelSheet;
