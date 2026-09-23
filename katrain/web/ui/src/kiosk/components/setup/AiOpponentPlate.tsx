import { useTranslation } from '../../../hooks/useTranslation';
import { interpolate } from '../../utils/interpolate';

/**
 * 屏 09 的签名件 —— 一张 56 高的「当前对手名牌」。
 *
 * ## 为什么读数要搬到名牌上
 *
 * `KioskStepTrack` 自带一行 `.catmeta` 读数(「第 22 / 39 档 · 展示 Elo 1500」)。
 * 屏 09 要在 400px 视口里放下四组设置,那一行 20px 省下来正好是「怎么落子」
 * 那句提示的位置。更要紧的是:**读数和对手是同一件事**,分两行写,推轨的时候
 * 眼睛要在两处之间来回跳。
 *
 * ## 为什么是 `<button>`
 *
 * 39 档的轨每档约 8px,跨到远处只能长按连发。名牌点开是**唯一**能一步跳到
 * 任意一档的路。⚠️ 它是 `<button>`,给了背景就必须同时给 `color` ——
 * 不给的话 `h4` 继承浏览器默认纯黑,在青毡底上看不见(2026-09-23 实际发生过)。
 */
interface AiOpponentPlateProps {
  name: string;
  levelName: string;
  displayElo: number;
  refRank?: string;
  index: number;
  total: number;
  onOpen: () => void;
  testId?: string;
}

const AiOpponentPlate = ({
  name, levelName, displayElo, refRank, index, total, onOpen, testId,
}: AiOpponentPlateProps) => {
  const { t } = useTranslation();
  const rung = interpolate(t('platform:rung_n', '第 {i} / {n} 档'), { i: index + 1, n: total });
  return (
    <button
      type="button"
      className="aiplate"
      data-testid={testId}
      aria-live="polite"
      aria-label={interpolate(
        t('platform:plate_aria', '当前对手 {name} {level}，{rung}；点开看全部'),
        { name, level: levelName, rung },
      )}
      onClick={onOpen}
    >
      <span className="av" aria-hidden="true">{name.slice(0, 1)}</span>
      <div>
        <h4>{name} · {levelName}</h4>
        <p>
          {interpolate(t('platform:display_elo', '展示 Elo {v}'), { v: displayElo })}
          {refRank ? <> · {interpolate(t('platform:ref_rank', '对标{r}'), { r: refRank })}</> : null}
        </p>
      </div>
      <b className="rung">{rung}</b>
    </button>
  );
};

export default AiOpponentPlate;
