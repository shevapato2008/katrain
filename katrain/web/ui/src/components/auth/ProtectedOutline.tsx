import { interpolate } from '../../kiosk/utils/interpolate';
import { accessMetadata, type AccessFeature } from './accessPolicy';
import { useTranslation } from '../../hooks/useTranslation';

const GhostRow = () => <div className="access-ghost-row"><span className="access-ghost-avatar" /><span className="access-ghost-copy"><i /><i /></span><span className="access-ghost-spacer" /><span className="access-ghost-copy"><i /><i /></span></div>;
/** Static public shape only. Never render protected children or business records underneath blur. */
export function ProtectedOutline({ surface, feature }: { surface: 'galaxy' | 'kiosk'; feature: AccessFeature }) {
  const { t } = useTranslation();
  const metadata = accessMetadata[feature];
  const kiosk = surface === 'kiosk';
  if (feature === 'membership') return <div className={`access-outline access-${surface}`} data-testid="protected-outline" aria-hidden="true">
    <header className="access-page-head"><span className="access-back">←{kiosk && interpolate(t(" {value1}", " {value1}"), { value1: t('membership:back_to_play', '返回对弈') })}</span><div><h1>{t('membership:auth_label', '会员与用量')}</h1>{!kiosk && <p>{t('membership:auth_description', '登录后查看会员用量、API 积分与订单。')}</p>}</div></header>
    <section className="access-panel access-stage"><div><h2>{t('membership:auth_label', '会员与用量')}</h2><div className="access-stage-lines"><i /><i /><i /><i /></div></div><div><h2>{t('membership:auth_after_login', '登录后使用')}</h2><span className="access-ghost-avatar" /><div className="access-stage-lines"><i /><i /><i /></div></div></section>
  </div>;
  return <div className={`access-outline access-${surface}`} data-testid="protected-outline" aria-hidden="true">
    <header className="access-page-head"><span className="access-back">←{kiosk && t(" 返回对弈", " 返回对弈")}</span><div><h1>{kiosk && feature === 'hall' ? t("在线大厅", "在线大厅") : t(metadata.label, metadata.label)}</h1>{!kiosk && <p>{feature === 'hall' ? t("选择空闲棋友，或一键匹配同段位对手。所有大厅对局均不计升降段位。", "选择空闲棋友，或一键匹配同段位对手。所有大厅对局均不计升降段位。") : t(metadata.description, metadata.description)}</p>}</div></header>
    {feature === 'hall' ? <>
      {kiosk && <div className="access-section-label">{t("开一局", "开一局")} <em>Start</em></div>}
      <div className="access-intros"><section className="access-intro"><span>{t("棋", "棋")}</span><div><strong>{kiosk ? t("快速匹配", "快速匹配") : t("来下一局", "来下一局")}</strong><small>{t("匹配同段位对手，或直接邀请棋友", "匹配同段位对手，或直接邀请棋友")}</small></div>{!kiosk && <span className="access-static-button">{t("快速匹配 →", "快速匹配 →")}</span>}</section>{kiosk && <section className="access-intro"><span>{t("友", "友")}</span><div><strong>{t("邀请棋友", "邀请棋友")}</strong><small>{t("直接邀请任意段位的空闲棋友", "直接邀请任意段位的空闲棋友")}</small></div></section>}</div>
      {kiosk && <div className="access-section-label">{t("对战大厅", "对战大厅")} <em>Lobby</em></div>}
      <div className="access-columns"><section className="access-panel"><h2>{t("进行中的对局", "进行中的对局")}</h2><div className="access-rows">{Array.from({length: kiosk ? 4 : 3}, (_, i) => <GhostRow key={i} />)}</div>{!kiosk && <p>{t("点击对局即可观战；自己的对局可返回棋盘。", "点击对局即可观战；自己的对局可返回棋盘。")}</p>}</section>{!kiosk && <section className="access-panel access-peers"><h2>{t("在线棋友", "在线棋友")}</h2><div className="access-ghost-filter">{t("全部棋友　同段位　我的关注", "全部棋友　同段位　我的关注")}</div><div className="access-rows">{Array.from({length:4}, (_, i) => <GhostRow key={i} />)}</div></section>}</div>
    </> : <section className="access-panel access-stage"><div><h2>{feature === 'rated' ? t("当前段位", "当前段位") : feature === 'reports' ? t("我的棋谱", "我的棋谱") : t(metadata.label, metadata.label)}</h2><div className="access-stage-lines"><i /><i /><i /><i /></div></div><div><h2>{feature === 'rated' ? t("本局挑战", "本局挑战") : feature === 'reports' ? t("复盘报告", "复盘报告") : t("登录后使用", "登录后使用")}</h2><span className="access-ghost-avatar" /><div className="access-stage-lines"><i /><i /><i /></div></div></section>}
  </div>;
}
