import { Icon, type IconName } from './icons';

const RING_R = 18;                       // (40 − 4) / 2,见下方注释
const RING_C = 2 * Math.PI * RING_R;

/**
 * §8 一级页模式卡。**所有一级页的卡片按钮都是这一种规格:220×76,40 方衬在左,
 * 标题+副标在右,间距 12**(tokens.css:572-587 给全)。不许某个模块自己另做一套尺寸
 * 或把图标挪到上面 —— 那是「切模块不跳」的另一种破法:框没跳,**手要去够的目标跳了**。
 *
 * 进度环卡不是新构造,是同一张卡换个衬(`.kiosk-card__tile.is-ring`):
 * 几何一个字不改,只把方衬里的图标换成环。环的画法逐行照抄稿子的脚本
 * (`sample-go/go-kiosk.tmpl.html:953-963`):
 *   · 衬 40 方、环描边 4 ⇒ 半径 (40 − 4) / 2 = 18,viewBox 0 0 40 40
 *   · 底圈永远画(`--hair`),进度圈只在 pct > 0 时画 —— 0% 画一段圆头短弧会看成「有一点点」
 *   · **100% 走 `--good`,不走强调色**:棋种把强调色换成别的时,「进行中」和「学完了」
 *     必须还分得开。围棋这两个色恰好同值(go-tokens.css 里注了),所以围棋这一屏上
 *     区分靠的是那圈画没画满 —— 这是巧合不是设计,别据此把这条规则删掉。
 *   · 旋转 −90°(起点回到 12 点)由 tokens.css:494 给,这里不重复写
 *
 * 值读不到时环里写「—」不写 0%(G8:0% 是一个事实断言,而我们并不知道)。
 */
export function KioskCard({ title, sub, icon, ring, current, soon, todo, dot, onClick, ariaLabel }: {
  title: string;
  sub: string;
  icon?: IconName;
  ring?: number | null;      // undefined = 不是环卡;null = 是环卡但读不到值 ⇒ 写「—」
  current?: boolean;
  soon?: string;             // 文案由调用方给(「即将上线」/「未录制」),不许写「锁定」
  todo?: boolean;
  dot?: boolean;
  onClick?: () => void;
  ariaLabel?: string;
}) {
  const cls = ['kiosk-card', current && 'is-current', soon && 'is-soon', todo && 'is-todo']
    .filter(Boolean).join(' ');
  const isRing = ring !== undefined;
  const pct = ring == null ? null : Math.max(0, Math.min(100, Math.round(ring)));
  return (
    <button
      type="button"
      className={cls}
      // 可及名要把**状态**一起带上:`.dot`(已连接那颗绿点)和 `.soon` 徽标都是纯视觉,
      // 只报标题的话,读屏的人拿到的三张平台卡一模一样 —— 分不出哪张连上了、哪张还没通。
      aria-label={ariaLabel ?? [title, sub, soon].filter(Boolean).join('，')}
      disabled={Boolean(soon || todo)}
      onClick={onClick}
    >
      <span className={`kiosk-card__tile${isRing ? ' is-ring' : ''}`}>
        {isRing ? (
          <>
            <svg viewBox="0 0 40 40" aria-hidden="true">
              <circle cx="20" cy="20" r={RING_R} fill="none" stroke="var(--hair)" strokeWidth="4" />
              {pct != null && pct > 0 && (
                <circle
                  cx="20" cy="20" r={RING_R} fill="none"
                  stroke={pct >= 100 ? 'var(--good)' : 'var(--accent)'}
                  strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={`${(RING_C * pct / 100).toFixed(2)} ${RING_C.toFixed(2)}`}
                />
              )}
            </svg>
            <b>{pct == null ? '—' : `${pct}%`}</b>
          </>
        ) : icon && <Icon name={icon} />}
      </span>
      <span className="kiosk-card__t"><b>{title}</b><em>{sub}</em></span>
      {dot && <span className="dot" aria-hidden="true" />}
      {soon && <span className="soon">{soon}</span>}
    </button>
  );
}
