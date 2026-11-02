import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { formatPoints, formatSavings, usagePercent } from '../../../features/membership/presentation';
import type { BillingOrder, CreateBillingOrder, MembershipPeriod } from '../../../features/membership/types';
import { useMembership } from '../../../features/membership/useMembership';
import { KioskActions } from '../../shell/KioskActions';
import { KioskPagebar } from '../../shell/KioskPagebar';
import { KioskScrollZone } from '../../shell/KioskScrollZone';
import { KioskSecLabel } from '../../shell/KioskSecLabel';
import { Icon } from '../../shell/icons';
import { useKioskMembershipOrder } from './useKioskMembershipOrder';
import './membership.css';

type MembershipTab = 'usage' | 'topup' | 'plans';
type MembershipInfo = 'quota' | 'pricing';
const tabs = [['usage', '用量'], ['topup', 'API充值'], ['plans', '会员']] as const;
const Num = ({ children }: { children: ReactNode }) => <span className="km-num">{children}</span>;
const money = (fen: number) => (fen / 100).toFixed(2);
const date = (value: string | null | undefined, full = false) => value && Number.isFinite(Date.parse(value))
  ? new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: full ? 'numeric' : undefined, month: '2-digit', day: '2-digit', ...(full ? {} : { hour: '2-digit', minute: '2-digit', hour12: false }) }).format(new Date(value))
  : '待确认';
const countdown = (seconds: number | null) => {
  if (seconds === null) return '待同步';
  if (seconds === 0) return '等待云端核对';
  const days = Math.floor(seconds / 86400);
  return `${days ? `${days}天 ` : ''}${String(Math.floor(seconds % 86400 / 3600)).padStart(2, '0')}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
};

function InfoButton({ kind, onOpen }: { kind: MembershipInfo; onOpen: (kind: MembershipInfo) => void }) {
  return <button type="button" className="km-info" aria-label={kind === 'quota' ? '会员额度与优惠说明' : 'API计价说明'} onClick={() => onOpen(kind)}><Icon name="info" /></button>;
}

/** Local overlay remains inside the scaled Kiosk canvas; no document-body portal. */
function CanvasDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLButtonElement>('button')?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);
  return <div className="km-backdrop" onKeyDown={event => {
    if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]') ?? []);
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }}><section className="km-dialog" role="dialog" aria-modal="true" aria-label={title} ref={dialog}>
    <header className="km-dialog-header"><h2>{title}</h2><button type="button" className="km-close" aria-label="关闭" onClick={onClose}><Icon name="arrow-left" /></button></header>
    {children}
  </section></div>;
}

function UsageWindow({ kind, period, seconds }: { kind: 'term' | 'week'; period: MembershipPeriod | null; seconds: number | null }) {
  const label = kind === 'term' ? '本期' : '本周';
  const percent = usagePercent(period, seconds !== 0);
  const known = percent !== '—' && period !== null;
  return <article className="km-limit">
    <div className="km-limit-heading"><strong>{label}</strong><span>剩余 <strong><Num>{percent}</Num></strong></span></div>
    {known ? <div className="km-progress" role="progressbar" aria-label={`${label}剩余比例`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={period.percent}><i style={{ width: percent }} /></div> : <p className="km-note">额度待云端核对</p>}
    <div className="km-limit-detail"><span>{known ? <>已用及分析中 <Num>{(100 - period.percent).toFixed(1)}%</Num></> : '剩余尚未确认'}</span><span>分析中的用量已计入</span></div>
    <div className="km-limit-reset"><span>{kind === 'term' ? '本期到期' : '周一零点重置'} · 北京时间</span><time dateTime={period?.reset_at} title={date(period?.reset_at)}><Num>{countdown(seconds)}</Num></time></div>
  </article>;
}

function OrderReceipt({ order }: { order: BillingOrder }) {
  const paid = order.status === 'paid';
  const states: Record<BillingOrder['status'], string> = { pending: '等待服务端支付确认', paid: '服务端已确认支付', expired: '订单已过期', failed: '订单未完成', refunded: '订单已退款' };
  return <>
    <div className="km-order-summary"><div><strong>{order.kind === 'topup' ? 'API积分充值' : '会员购买'}</strong><span className="km-note">订单 <Num>{order.id}</Num></span></div><strong>¥<Num>{money(order.amount_fen)}</Num></strong></div>
    <p className="km-order-state" role="status">{states[order.status]}</p>
    {order.payments_mode === 'mock' && <p className="km-test">TEST模拟订单 · 不会真实收款</p>}
    {paid ? <>
      <p className="km-note">确认时间 <Num>{date(order.paid_at)}</Num> · 北京时间</p>
      {order.kind === 'membership' && order.fulfillment && <p className="km-note">生效 <Num>{date(order.fulfillment.starts_at, true)}</Num> 至 <Num>{date(order.fulfillment.ends_at, true)}</Num> · 以此回执为准</p>}
      {order.kind === 'topup' && order.fulfillment?.credits !== undefined && <p className="km-note">到账 <Num>{formatPoints(order.fulfillment.credits)}</Num> 积分</p>}
      <p className="km-note">账户用量正在重新同步，余额与权益以云端快照为准。</p>
    </> : order.status === 'pending' ? <>
      {order.kind === 'membership' && <><p className="km-note">预计 <Num>{date(order.estimated_starts_at, true)}</Num> 至 <Num>{date(order.estimated_ends_at, true)}</Num> · 北京时间</p><p className="km-note">已有会员将顺延至已购周期结束后生效；现有用量保留，最终时间以支付回执为准。</p></>}
      <p className="km-note">订单有效至 <Num>{date(order.expires_at)}</Num> · 北京时间</p>
      <p className="km-note">{order.payments_mode === 'mock' ? '测试环境由服务端模拟支付结果，此页不会触发支付或自行发放权益。' : '支付入口尚未接通，请稍后查看订单状态。'}</p>
    </> : <p className="km-note">本页不会自行发放权益；需要时返回重新选择。</p>}
  </>;
}

export default function MembershipPage() {
  const navigate = useNavigate();
  const { identityKey, status: authStatus } = useAuth();
  const { catalog, usage, status, countdowns, refresh } = useMembership();
  const checkout = useKioskMembershipOrder(catalog?.environment);
  const [tab, setTab] = useState<MembershipTab>('usage');
  const [info, setInfo] = useState<MembershipInfo | null>(null);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const ready = status === 'ready' && authStatus === 'authenticated' && identityKey !== null;
  const boundaryPending = ready && [countdowns.term, countdowns.week, countdowns.free].includes(0);
  const usable = ready && !boundaryPending;
  const paymentReady = usable && catalog?.capabilities.orders === true && usage?.capabilities.orders === true
    && catalog.payments_mode === 'mock' && catalog.environment.toLowerCase() === 'test' && catalog.payments_mode === usage.payments_mode;
  const selected = catalog?.topups.find(option => option.sku === selectedSku) ?? catalog?.topups[0];
  const activePlan = usable ? usage?.plan.current : null;
  const wallet = usable ? usage?.wallet : null;
  const multiplier = catalog && catalog.profiles.normal.credits_per_position > 0
    ? catalog.profiles.advanced.credits_per_position / catalog.profiles.normal.credits_per_position : null;
  const paymentReason = !usable ? '账号和额度确认后才可购买' : !paymentReady ? '支付暂未开放' : null;
  const environment = catalog?.environment.toLowerCase();
  const isTest = environment === 'test' || environment === 'development';
  useEffect(() => { setInfo(null); setSelectedSku(null); }, [identityKey, authStatus]);

  const buy = (sku: string, membership: boolean) => {
    if (!paymentReady || !catalog || checkout.creating) return;
    if (membership && (!catalog.capabilities.membership || !usage?.capabilities.membership || catalog.membership_mode !== 'enabled'
      || !catalog.plans.find(plan => `membership_${plan.code}` === sku)?.sale_enabled)) return;
    if (!membership && !catalog.topups.some(option => option.sku === sku)) return;
    void checkout.create({ sku: sku as CreateBillingOrder['sku'], provider: catalog.payments_mode === 'mock' ? 'mock' : 'live', idempotency_key: crypto.randomUUID() });
  };
  const closeOrder = () => {
    const paid = checkout.order?.status === 'paid';
    checkout.close();
    if (paid) setTab('usage');
  };
  const headerState = boundaryPending ? '周期待核对' : status === 'loading' ? '正在同步' : status === 'error' ? '同步失败'
    : status === 'unauthenticated' ? '请先确认账户' : status === 'unavailable' ? '服务暂不可用' : isTest ? 'TEST · 测试环境' : '云端已同步';
  const emptyTitle = status === 'error' ? '暂时无法同步用量' : status === 'unavailable' ? '会员服务暂不可用' : status === 'unauthenticated' ? '请先确认账户身份' : '额度正在确认';
  const quotaInfo = <>
    <p>同一结果包含领地与支招，重复查看不重复扣费。高级分析消耗普通分析的<Num>{multiplier ?? '—'}</Num>倍额度。</p>
    <p>每周最多盘数按<Num>300</Num>手普通报告估算，受本期剩余限制。本期普通报告参考：{catalog?.plans.map((plan, i) => <span key={plan.code}>{i > 0 ? '、' : ''}{plan.name}<Num>{plan.term_report_reference}</Num>盘</span>)}。</p>
    <p>会员按购买周期到期，每周在北京时间周一零点重置。本期与本周的剩余比例分别计算；分析中的用量已计入。</p>
    <p>两项剩余都足够才使用会员，否则整次使用API积分，不拆分扣费。分析前确认来源与报价，积分不足时需手动充值或等待重置。</p>
    <p>优惠与API普通分析相比，按本期额度全部用满计算；未用满时实际优惠随用量变化。Free仅有免费普通报告资格，不赠通用分析额度。</p>
  </>;
  const pricingInfo = <>
    <p>余额以<Num>0.01</Num>积分精度显示。普通每局面<Num>{catalog ? formatPoints(catalog.profiles.normal.credits_per_position) : '—'}</Num>积分，高级每局面<Num>{catalog ? formatPoints(catalog.profiles.advanced.credits_per_position) : '—'}</Num>积分。</p>
    <p><Num>N</Num>手报告含初始局面，共<Num>N+1</Num>个局面；实际扣费以分析前的棋谱报价为准。</p>
    <p>会员本期、本周两项剩余须同时足够本次分析，否则整次使用API积分，不拆分扣费。不自动充值人民币。</p>
    <p>离线或额度未知时先同步。已拥有结果可重复查看，领地与支招包含在同一结果内。</p>
  </>;

  const account = <aside className="km-aside">
    <div className="km-account"><strong>{usable ? activePlan?.name ?? 'Free' : '待同步'}</strong><span>{usable ? '当前权益' : '尚未确认'}</span></div>
    <p>{!usable ? '账号权益确认后显示' : activePlan ? <>有效至 <Num>{date(activePlan.ends_at, true)}</Num></> : '免费报告资格以云端核验为准'}</p>
    <div className="km-wallet"><span>API余额</span><strong><Num>{formatPoints(wallet?.credits)}</Num> 积分</strong><span>会员优先，API积分接续</span></div>
    <div className={`km-sync${usable ? '' : ' is-stale'}`}><span>{usable ? '已同步' : '额度尚未确认'}</span>{usable && usage && <time dateTime={usage.server_now}><Num>{new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(usage.server_now))}</Num></time>}</div>
    {usable && usage?.plan.next ? <p>下期 {usage.plan.next.name} · <Num>{date(usage.plan.next.starts_at, true)}</Num>生效</p> : <p>分析前确认来源与报价</p>}
    <KioskActions className="km-account-actions" ariaLabel="账户操作" actions={[
      { key: 'topup', icon: 'squares-four', label: 'API充值', onClick: () => setTab('topup') },
      { key: 'plans', icon: 'crown-simple', label: '查看会员', onClick: () => setTab('plans') },
    ]} />
  </aside>;

  return <div className="km-page" data-testid="kiosk-membership-page">
    <KioskPagebar backLabel="返回设置" onBack={() => navigate('/kiosk/settings')} title="会员与充值" status={<span className={usable && !isTest ? 'km-header-ready' : 'km-header-status'} role="status">{headerState}</span>} action={{ icon: 'clock-counter-clockwise', label: '订单记录', onClick: () => void checkout.openHistory() }} />
    <nav className="km-tabs" role="tablist" aria-label="会员与充值">{tabs.map(([key, label]) => <button key={key} type="button" id={`km-tab-${key}`} role="tab" aria-selected={tab === key} aria-controls={tab === key ? `km-panel-${key}` : undefined} tabIndex={tab === key ? 0 : -1} onClick={() => setTab(key)} onKeyDown={event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const next = tabs[(tabs.findIndex(([id]) => id === tab) + (event.key === 'ArrowRight' ? 1 : 2)) % tabs.length][0];
      setTab(next); document.getElementById(`km-tab-${next}`)?.focus();
    }}>{label}</button>)}</nav>
    <KioskScrollZone className="km-scroll" resetKey={tab}>
      <section className="km-body" id={`km-panel-${tab}`} role="tabpanel" aria-labelledby={`km-tab-${tab}`}>
        {tab === 'usage' && <div className="km-usage"><section className="km-resource">
          {!usable ? <div className="km-empty" role="status"><h2>{boundaryPending ? '周期额度待核对' : emptyTitle}</h2><p>确认前不显示剩余比例，也不创建订单。</p><button type="button" className="km-primary" onClick={() => void refresh()} disabled={status === 'loading'}>重新同步</button></div>
            : activePlan ? <>
              <div className="km-available"><span>{usage?.term?.remaining === 0 || usage?.week?.remaining === 0 ? '会员额度不足时使用API积分' : '会员额度优先用于分析'}</span><InfoButton kind="quota" onOpen={setInfo} /></div>
              <UsageWindow kind="term" period={usage?.term ?? null} seconds={countdowns.term} />
              <UsageWindow kind="week" period={usage?.week ?? null} seconds={countdowns.week} />
              <p className="km-footnote">两项剩余须同时足够本次分析；不足时整次使用API积分。<br />一次结果含领地与支招，重复查看不重复扣费。</p>
            </> : <section className="km-free"><KioskSecLabel zh="每周免费普通报告" action={<InfoButton kind="quota" onOpen={setInfo} />} />
              {usage?.free?.eligible ? <><p className="km-free-count">剩余 <Num>{usage.free.remaining}</Num> / <Num>{usage.free.limit}</Num> 份</p><p>普通报告资格，不赠通用分析额度</p><p>周一零点重置 · 北京时间</p><p><Num>{countdown(countdowns.free)}</Num></p></>
                : <><h2>免费报告资格待核验</h2><p>请先完成账户验证，核验通过后显示本周资格。</p></>}
              <p className="km-footnote">已拥有结果可反复查看；领地与支招含在同一结果内。</p>
            </section>}
        </section>{account}</div>}
        {tab === 'plans' && <section className="km-plans">
          <KioskSecLabel zh="会员" value="额度用满时，比API更省" action={<InfoButton kind="quota" onOpen={setInfo} />} />
          {catalog ? <div className="km-plan-grid">{catalog.plans.map(plan => {
            const current = activePlan?.code === plan.code;
            const unavailable = !plan.sale_enabled;
            const enabled = paymentReady && catalog.capabilities.membership && usage?.capabilities.membership && catalog.membership_mode === 'enabled' && !unavailable;
            return <article key={plan.code} className={`km-plan${current ? ' is-current' : ''}${unavailable ? ' is-unavailable' : ''}`}>
              <div className="km-plan-head"><strong>{plan.name}</strong><span>{unavailable ? '暂未开放' : current ? '当前会员' : ''}</span></div>
              <div className="km-plan-price">¥<Num>{money(plan.amount_fen)}</Num> <small>/ <Num>{plan.term_days}</Num>天</small></div>
              <p className="km-saving">比API约省 <Num>{formatSavings(plan.full_use_savings_percent)}</Num></p>
              <div className="km-report-reference"><span>普通报告 · <Num>{plan.term_days}</Num>天共约<Num>{plan.term_report_reference}</Num>盘</span><strong>每周最多约 <Num>{plan.week_report_reference}</Num> 盘</strong></div>
              <button type="button" className={plan.code === 'pro' ? 'km-primary' : ''} disabled={!enabled || checkout.creating} onClick={() => buy(`membership_${plan.code}`, true)}>{unavailable ? '暂未开放' : `${current ? '续费' : '选择'} ${plan.name}`}</button>
            </article>;
          })}</div> : <div className="km-empty"><h2>会员目录待同步</h2><p>目录确认后显示价格与权益。</p><button type="button" onClick={() => void refresh()}>重新同步</button></div>}
          <div className="km-plan-footer"><p>按<Num>300</Num>手估算，受本期剩余限制；高级约<Num>{multiplier ?? '—'}</Num>倍消耗<br />优惠按本期额度用满计算；未用满时，实际优惠随用量变化</p>{paymentReason && <span role="status">{paymentReason}</span>}</div>
        </section>}
        {tab === 'topup' && <section className="km-topup"><article className="km-api-rates">
          <KioskSecLabel zh="API充值 · 按用量付费" action={<InfoButton kind="pricing" onOpen={setInfo} />} />
          <div className="km-rate"><span>普通分析</span><strong><Num>{catalog ? formatPoints(catalog.profiles.normal.credits_per_position) : '—'}</Num> 积分 / 手</strong></div>
          <div className="km-rate"><span>高级分析</span><strong><Num>{catalog ? formatPoints(catalog.profiles.advanced.credits_per_position) : '—'}</Num> 积分 / 手</strong></div>
          <p className="km-report-quote"><Num>300</Num>手报告 · 普通 <Num>{catalog ? formatPoints(301 * catalog.profiles.normal.credits_per_position) : '—'}</Num> 积分<br />高级 <Num>{catalog ? formatPoints(301 * catalog.profiles.advanced.credits_per_position) : '—'}</Num> 积分，均含初始局面</p>
          <p className="km-footnote">两项会员剩余足够时优先使用会员额度，否则整次使用API积分。<br />分析前确认来源与报价，不自动充值。</p>
          <div className="km-alternative"><span>经常使用，会员可更省</span><button type="button" onClick={() => setTab('plans')}>比较会员</button></div>
        </article><aside className="km-recharge">
          <div className="km-recharge-balance"><span>当前API余额</span><strong><Num>{formatPoints(wallet?.credits)}</Num> 积分</strong></div>
          <p className="km-exchange">{selected && selected.amount_fen > 0 ? <><Num>1</Num>元 = <Num>{Number((selected.credits / selected.amount_fen).toFixed(2))}</Num>积分</> : '充值目录待同步'}</p>
          <div className="km-amounts" role="group" aria-label="选择API充值金额">{catalog?.topups.map(option => <button key={option.sku} type="button" aria-label={`¥${money(option.amount_fen)} ${formatPoints(option.credits)}积分`} aria-pressed={selected?.sku === option.sku} onClick={() => setSelectedSku(option.sku)}><strong>¥<Num>{money(option.amount_fen)}</Num></strong><span><Num>{formatPoints(option.credits)}</Num>积分</span></button>)}</div>
          <p className="km-selected">到账 <Num>{formatPoints(selected?.credits)}</Num> 积分</p>
          <button type="button" className="km-primary" disabled={!paymentReady || !selected || checkout.creating} onClick={() => selected && buy(selected.sku, false)}>充值{selected ? <> ¥<Num>{money(selected.amount_fen)}</Num></> : ''}</button>
          <p className="km-footnote" role="status">{paymentReason ?? (isTest ? 'TEST模拟订单 · 不会真实收款' : '付款前核对订单金额')}</p>
        </aside></section>}
      </section>
    </KioskScrollZone>
    {info && <CanvasDialog title={info === 'quota' ? '会员额度与优惠说明' : 'API计价说明'} onClose={() => setInfo(null)}><KioskScrollZone grow className="km-dialog-copy" resetKey={info}>{info === 'quota' ? quotaInfo : pricingInfo}</KioskScrollZone><footer className="km-dialog-actions"><button type="button" className="km-primary" onClick={() => setInfo(null)}>知道了</button></footer></CanvasDialog>}
    {checkout.history && <CanvasDialog title="订单记录" onClose={checkout.close}>
      <KioskScrollZone grow className="km-order-history">
        {checkout.history.loading ? <p className="km-note" role="status">正在同步订单…</p> : checkout.history.error ? <p className="km-note" role="status">{checkout.history.error}</p> : checkout.history.orders.length ? checkout.history.orders.map(order => <button key={order.id} type="button" className="km-history-row" aria-label={`查看订单 ${order.id}`} onClick={() => checkout.openOrder(order)}>
          <span><strong>{order.kind === 'membership' ? '会员购买' : 'API充值'} · <Num>{date(order.created_at)}</Num></strong><span className="km-note"><Num>{order.id}</Num></span></span>
          <span><strong>¥<Num>{money(order.amount_fen)}</Num></strong><span className="km-note">{({ pending: '待付款', paid: '已支付', expired: '已过期', failed: '未完成', refunded: '已退款' })[order.status]}</span></span>
        </button>) : <p className="km-note">暂无订单记录</p>}
      </KioskScrollZone>
      <footer className="km-dialog-actions"><button type="button" onClick={() => void checkout.openHistory()} disabled={checkout.history.loading}>重新同步</button><button type="button" className="km-primary" onClick={checkout.close}>返回</button></footer>
    </CanvasDialog>}
    {(checkout.creating || checkout.order || checkout.error) && <CanvasDialog title="订单确认" onClose={closeOrder}>
      {checkout.order ? <OrderReceipt order={checkout.order} /> : <p className="km-order-state" role="status">{checkout.creating ? '正在创建订单…' : '订单待确认'}</p>}
      {checkout.error && <p className="km-note" role="status">{checkout.error}</p>}
      <footer className="km-dialog-actions">{checkout.error && !checkout.order && <button type="button" onClick={() => void checkout.openHistory()}>订单记录</button>}<button type="button" className="km-primary" onClick={closeOrder}>{checkout.order?.status === 'paid' ? '返回用量' : '返回选择'}</button></footer>
    </CanvasDialog>}
  </div>;
}
