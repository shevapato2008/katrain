import { accessMetadata, type AccessFeature } from './accessPolicy';

const GhostRow = () => <div className="access-ghost-row"><span className="access-ghost-avatar" /><span className="access-ghost-copy"><i /><i /></span><span className="access-ghost-spacer" /><span className="access-ghost-copy"><i /><i /></span></div>;
/** Static public shape only. Never render protected children or business records underneath blur. */
export function ProtectedOutline({ surface, feature }: { surface: 'galaxy' | 'kiosk'; feature: AccessFeature }) {
  const metadata = accessMetadata[feature];
  const kiosk = surface === 'kiosk';
  return <div className={`access-outline access-${surface}`} data-testid="protected-outline" aria-hidden="true">
    <header className="access-page-head"><span className="access-back">←{kiosk && ' 返回对弈'}</span><div><h1>{kiosk && feature === 'hall' ? '在线大厅' : metadata.label}</h1>{!kiosk && <p>{feature === 'hall' ? '选择空闲棋友，或一键匹配同段位对手。所有大厅对局均不计升降段位。' : metadata.description}</p>}</div></header>
    {feature === 'hall' ? <>
      {kiosk && <div className="access-section-label">开一局 <em>Start</em></div>}
      <div className="access-intros"><section className="access-intro"><span>棋</span><div><strong>{kiosk ? '快速匹配' : '来下一局'}</strong><small>匹配同段位对手，或直接邀请棋友</small></div>{!kiosk && <span className="access-static-button">快速匹配 →</span>}</section>{kiosk && <section className="access-intro"><span>友</span><div><strong>邀请棋友</strong><small>直接邀请任意段位的空闲棋友</small></div></section>}</div>
      {kiosk && <div className="access-section-label">对战大厅 <em>Lobby</em></div>}
      <div className="access-columns"><section className="access-panel"><h2>进行中的对局</h2><div className="access-rows">{Array.from({length: kiosk ? 4 : 3}, (_, i) => <GhostRow key={i} />)}</div>{!kiosk && <p>点击对局即可观战；自己的对局可返回棋盘。</p>}</section>{!kiosk && <section className="access-panel access-peers"><h2>在线棋友</h2><div className="access-ghost-filter">全部棋友　同段位　我的关注</div><div className="access-rows">{Array.from({length:4}, (_, i) => <GhostRow key={i} />)}</div></section>}</div>
    </> : <section className="access-panel access-stage"><div><h2>{feature === 'rated' ? '当前段位' : feature === 'reports' ? '我的棋谱' : metadata.label}</h2><div className="access-stage-lines"><i /><i /><i /><i /></div></div><div><h2>{feature === 'rated' ? '本局挑战' : feature === 'reports' ? '复盘报告' : '登录后使用'}</h2><span className="access-ghost-avatar" /><div className="access-stage-lines"><i /><i /><i /></div></div></section>}
  </div>;
}
