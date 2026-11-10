import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { usagePercent } from '../../../features/membership/presentation';
import type { BillingOrder, CreateBillingOrder, MembershipPeriod } from '../../../features/membership/types';
import { WechatNativePayment } from '../../../features/membership/WechatNativePayment';
import { useMembership } from '../../../features/membership/useMembership';
import { useMembershipI18n } from '../../../features/membership/useMembershipI18n';
import { KioskActions } from '../../shell/KioskActions';
import { KioskPagebar } from '../../shell/KioskPagebar';
import { KioskScrollZone } from '../../shell/KioskScrollZone';
import { KioskSecLabel } from '../../shell/KioskSecLabel';
import { Icon } from '../../shell/icons';
import { useKioskMembershipOrder } from './useKioskMembershipOrder';
import './membership.css';

type MembershipTab = 'usage' | 'topup' | 'plans';
type MembershipInfo = 'quota' | 'pricing';
const Num = ({ children }: { children: ReactNode }) => <span className="km-num">{children}</span>;

function InfoButton({ kind, onOpen }: { kind: MembershipInfo; onOpen: (kind: MembershipInfo) => void }) {
  const { t } = useMembershipI18n();
  return <button type="button" className="km-info" aria-label={kind === 'quota' ? t('membership:kiosk_quota_help', '会员额度与优惠说明') : t('membership:kiosk_pricing_help', 'API计价说明')} onClick={() => onOpen(kind)}><Icon name="info" /></button>;
}

/** Local overlay remains inside the scaled Kiosk canvas; no document-body portal. */
function CanvasDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const { t } = useMembershipI18n();
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
    <header className="km-dialog-header"><h2>{title}</h2><button type="button" className="km-close" aria-label={t('membership:close', '关闭')} onClick={onClose}><Icon name="arrow-left" /></button></header>
    {children}
  </section></div>;
}

function UsageWindow({ kind, period, seconds }: { kind: 'term' | 'week'; period: MembershipPeriod | null; seconds: number | null }) {
  const { t, number, date, countdown } = useMembershipI18n();
  const label = kind === 'term' ? t('membership:kiosk_term', '本期') : t('membership:kiosk_week', '本周');
  const known = usagePercent(period, seconds !== 0) !== '—' && period !== null;
  const percent = known ? number(period.percent / 100, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }) : '—';
  return <article className="km-limit">
    <div className="km-limit-heading"><strong>{label}</strong><span>{t('membership:kiosk_remaining', '剩余')} <strong><Num>{percent}</Num></strong></span></div>
    {known ? <div className="km-progress" role="progressbar" aria-label={kind === 'term' ? t('membership:kiosk_term_remaining_aria', '本期剩余比例') : t('membership:kiosk_week_remaining_aria', '本周剩余比例')} aria-valuemin={0} aria-valuemax={100} aria-valuenow={period.percent}><i style={{ width: `${period.percent}%` }} /></div> : <p className="km-note">{t('membership:kiosk_quota_unconfirmed', '额度待云端核对')}</p>}
    <div className="km-limit-detail"><span>{known ? t('membership:kiosk_used_reserved', '已用及分析中 {percent}', { percent: number((100 - period.percent) / 100, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }) }) : t('membership:kiosk_remaining_unconfirmed', '剩余尚未确认')}</span><span>{t('membership:kiosk_reserved_included', '分析中的用量已计入')}</span></div>
    <div className="km-limit-reset"><span>{kind === 'term' ? t('membership:kiosk_term_expiry_beijing', '本期到期 · 北京时间') : t('membership:kiosk_week_reset_beijing', '周一零点重置 · 北京时间')}</span><time dateTime={period?.reset_at} title={date(period?.reset_at)}><Num>{countdown(seconds)}</Num></time></div>
  </article>;
}

function OrderReceipt({ order }: { order: BillingOrder }) {
  const { t, date, money, number } = useMembershipI18n();
  const paid = order.status === 'paid';
  const states: Record<BillingOrder['status'], string> = {
    pending: t('membership:kiosk_order_waiting_server', '等待服务端支付确认'),
    paid: t('membership:kiosk_order_server_paid', '服务端已确认支付'),
    expired: t('membership:kiosk_order_expired', '订单已过期'),
    failed: t('membership:kiosk_order_failed', '订单未完成'),
    refunded: t('membership:kiosk_order_refunded', '订单已退款'),
    cancelled: t('membership:order_cancelled', '订单已取消'),
  };
  return <>
    <div className={`km-order-summary${order.provider === 'wechat' ? ' km-order-summary--native' : ''}`}><div><strong>{order.kind === 'topup' ? t('membership:kiosk_api_points_topup', 'API积分充值') : t('membership:kiosk_membership_purchase', '会员购买')}</strong><span className="km-note">{t('membership:kiosk_order_id', '订单 {id}', { id: order.id })}</span></div><strong><Num>{money(order.amount_fen)}</Num></strong></div>
    {order.provider === 'wechat' ? <WechatNativePayment order={order} layout="kiosk" /> : <p className="km-order-state" role="status">{states[order.status]}</p>}
    {order.payments_mode === 'mock' && <p className="km-test">{t('membership:kiosk_test_order', 'TEST模拟订单 · 不会真实收款')}</p>}
    {paid ? <>
      <p className="km-note">{t('membership:kiosk_paid_time', '确认时间 {date} · 北京时间', { date: date(order.paid_at) })}</p>
      {order.kind === 'membership' && order.fulfillment && <p className="km-note">{t('membership:kiosk_membership_receipt_period', '生效 {start} 至 {end} · 北京时间 · 以此回执为准', { start: date(order.fulfillment.starts_at, true), end: date(order.fulfillment.ends_at, true) })}</p>}
      {order.kind === 'topup' && order.fulfillment?.credits !== undefined && <p className="km-note">{t('membership:kiosk_credited_points', '到账 {points} 积分', { points: number(order.fulfillment.credits / 100, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) })}</p>}
      <p className="km-note">{t('membership:kiosk_receipt_resync', '账户用量正在重新同步，余额与权益以云端快照为准。')}</p>
    </> : order.status === 'pending' ? <>
      {order.kind === 'membership' && <><p className="km-note">{t('membership:kiosk_estimated_period', '预计 {start} 至 {end} · 北京时间', { start: date(order.estimated_starts_at, true), end: date(order.estimated_ends_at, true) })}</p><p className="km-note">{t('membership:kiosk_membership_extension', '已有会员将顺延至已购周期结束后生效；现有用量保留，最终时间以支付回执为准。')}</p></>}
      <p className="km-note">{t('membership:kiosk_order_valid_until', '订单有效至 {date} · 北京时间', { date: date(order.expires_at) })}</p>
      {order.provider !== 'wechat' && <p className="km-note">{order.payments_mode === 'mock' ? t('membership:kiosk_mock_fulfillment', '测试环境由服务端模拟支付结果，此页不会触发支付或自行发放权益。') : t('membership:kiosk_payment_entry_pending', '支付入口尚未接通，请稍后查看订单状态。')}</p>}
    </> : <p className="km-note">{t('membership:kiosk_no_local_fulfillment', '本页不会自行发放权益；需要时返回重新选择。')}</p>}
  </>;
}

export default function MembershipPage() {
  const { t, locale, date, countdown, money, number } = useMembershipI18n();
  const tabs = [['usage', t('membership:usage', '用量')], ['topup', t('membership:api_topup', 'API充值')], ['plans', t('membership:plans', '会员')]] as const;
  const points = (credits: number | null | undefined) => typeof credits === 'number' && Number.isSafeInteger(credits) && credits >= 0
    ? number(credits / 100, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const navigate = useNavigate();
  const { identityKey, status: authStatus } = useAuth();
  const { catalog, usage, status, countdowns, refresh } = useMembership();
  const checkout = useKioskMembershipOrder(catalog?.environment);
  const [purchase, setPurchase] = useState<{ sku: CreateBillingOrder['sku']; amount: number; name: string } | null>(null);
  const [tab, setTab] = useState<MembershipTab>('usage');
  const [info, setInfo] = useState<MembershipInfo | null>(null);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const ready = status === 'ready' && authStatus === 'authenticated' && identityKey !== null;
  const boundaryPending = ready && [countdowns.term, countdowns.week, countdowns.free].includes(0);
  const usable = ready && !boundaryPending;
  const paymentReady = usable && catalog?.capabilities.orders === true && usage?.capabilities.orders === true
    && ((catalog.payments_mode === 'mock' && catalog.environment.toLowerCase() === 'test') || catalog.payments_mode === 'live') && catalog.payments_mode === usage.payments_mode;
  const selected = catalog?.topups.find(option => option.sku === selectedSku) ?? catalog?.topups[0];
  const activePlan = usable ? usage?.plan.current : null;
  const wallet = usable ? usage?.wallet : null;
  const multiplier = catalog && catalog.profiles.normal.credits_per_position > 0
    ? catalog.profiles.advanced.credits_per_position / catalog.profiles.normal.credits_per_position : null;
  const paymentReason = !usable ? t('membership:kiosk_purchase_after_sync', '账号和额度确认后才可购买') : !paymentReady ? t('membership:payments_disabled', '支付暂未开放') : null;
  const environment = catalog?.environment.toLowerCase();
  const isTest = environment === 'test' || environment === 'development';
  useEffect(() => { setInfo(null); setSelectedSku(null); setPurchase(null); }, [identityKey, authStatus]);

  const buy = (sku: string, membership: boolean) => {
    if (!paymentReady || !catalog || checkout.creating) return;
    if (membership && (!catalog.capabilities.membership || !usage?.capabilities.membership || catalog.membership_mode !== 'enabled'
      || !catalog.plans.find(plan => `membership_${plan.code}` === sku)?.sale_enabled)) return;
    if (!membership && !catalog.topups.some(option => option.sku === sku)) return;
    if (catalog.payments_mode === 'live') {
      const item = membership ? catalog.plans.find(plan => `membership_${plan.code}` === sku)! : catalog.topups.find(option => option.sku === sku)!;
      setPurchase({ sku: sku as CreateBillingOrder['sku'], amount: item.amount_fen, name: membership ? catalog.plans.find(plan => `membership_${plan.code}` === sku)!.name : t('membership:api_topup', 'API充值') });
    } else void checkout.create({ sku: sku as CreateBillingOrder['sku'], provider: 'mock', idempotency_key: crypto.randomUUID() });
  };
  const closeOrder = () => {
    const paid = checkout.order?.status === 'paid';
    checkout.close();
    setPurchase(null);
    if (paid) setTab('usage');
  };
  const headerState = boundaryPending ? t('membership:kiosk_period_pending', '周期待核对') : status === 'loading' ? t('membership:kiosk_syncing', '正在同步') : status === 'error' ? t('membership:kiosk_sync_failed', '同步失败')
    : status === 'unauthenticated' ? t('membership:kiosk_confirm_account', '请先确认账户') : status === 'unavailable' ? t('membership:kiosk_service_unavailable', '服务暂不可用') : isTest ? t('membership:kiosk_test_environment', 'TEST · 测试环境') : t('membership:kiosk_cloud_synced', '云端已同步');
  const emptyTitle = status === 'error' ? t('membership:kiosk_usage_sync_error', '暂时无法同步用量') : status === 'unavailable' ? t('membership:kiosk_membership_unavailable', '会员服务暂不可用') : status === 'unauthenticated' ? t('membership:kiosk_verify_identity', '请先确认账户身份') : t('membership:kiosk_quota_confirming', '额度正在确认');
  const planReferences = catalog?.plans.map(plan => t('membership:kiosk_plan_report_reference', '{plan}{reports}盘', { plan: plan.name, reports: number(plan.term_report_reference) })) ?? [];
  const quotaInfo = <>
    <p>{t('membership:kiosk_quota_result_help', '同一结果包含领地与支招，重复查看不重复扣费。高级分析消耗普通分析的{multiplier}倍额度。', { multiplier: multiplier === null ? '—' : number(multiplier) })}</p>
    <p>{t('membership:kiosk_quota_report_help', '每周最多盘数按{moves}手普通报告估算，受本期剩余限制。本期普通报告参考：{references}。', { moves: number(300), references: new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(planReferences) })}</p>
    <p>{t('membership:kiosk_quota_reset_help', '会员按购买周期到期，每周在北京时间周一零点重置。本期与本周的剩余比例分别计算；分析中的用量已计入。')}</p>
    <p>{t('membership:kiosk_quota_fallback_help', '两项剩余都足够才使用会员，否则整次使用API积分，不拆分扣费。分析前确认来源与报价，积分不足时需手动充值或等待重置。')}</p>
    <p>{t('membership:kiosk_quota_savings_help', '优惠与API普通分析相比，按本期额度全部用满计算；未用满时实际优惠随用量变化。Free仅有免费普通报告资格，不赠通用分析额度。')}</p>
  </>;
  const pricingInfo = <>
    <p>{t('membership:kiosk_pricing_rates_help', '余额以{precision}积分精度显示。普通每局面{normal}积分，高级每局面{advanced}积分。', { precision: number(0.01), normal: points(catalog?.profiles.normal.credits_per_position), advanced: points(catalog?.profiles.advanced.credits_per_position) })}</p>
    <p>{t('membership:kiosk_pricing_positions_help', 'N手报告含初始局面，共N+1个局面；实际扣费以分析前的棋谱报价为准。')}</p>
    <p>{t('membership:kiosk_pricing_fallback_help', '会员本期、本周两项剩余须同时足够本次分析，否则整次使用API积分，不拆分扣费。不自动充值人民币。')}</p>
    <p>{t('membership:kiosk_pricing_sync_help', '离线或额度未知时先同步。已拥有结果可重复查看，领地与支招包含在同一结果内。')}</p>
  </>;

  const account = <aside className="km-aside">
    <div className="km-account"><strong>{usable ? activePlan?.name ?? 'Free' : t('membership:kiosk_sync_pending', '待同步')}</strong><span>{usable ? t('membership:kiosk_current_benefits', '当前权益') : t('membership:kiosk_unconfirmed', '尚未确认')}</span></div>
    <p>{!usable ? t('membership:kiosk_benefits_after_sync', '账号权益确认后显示') : activePlan ? t('membership:kiosk_plan_valid_until', '有效至 {date} · 北京时间', { date: date(activePlan.ends_at, true) }) : t('membership:kiosk_free_cloud_verified', '免费报告资格以云端核验为准')}</p>
    <div className="km-wallet"><span>{t('membership:kiosk_api_balance', 'API余额')}</span><strong>{t('membership:kiosk_points_amount', '{points} 积分', { points: points(wallet?.credits) })}</strong><span>{t('membership:kiosk_member_then_api', '会员优先，API积分接续')}</span></div>
    <div className={`km-sync${usable ? '' : ' is-stale'}`}><span>{usable ? t('membership:kiosk_synced', '已同步') : t('membership:kiosk_quota_not_confirmed', '额度尚未确认')}</span>{usable && usage && <time dateTime={usage.server_now} title={date(usage.server_now)}><Num>{new Intl.DateTimeFormat(locale, { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(usage.server_now))}</Num></time>}</div>
    {usable && usage?.plan.next ? <p>{t('membership:kiosk_next_plan', '下期 {plan} · {date}生效 · 北京时间', { plan: usage.plan.next.name, date: date(usage.plan.next.starts_at, true) })}</p> : <p>{t('membership:kiosk_confirm_source_quote', '分析前确认来源与报价')}</p>}
    <KioskActions className="km-account-actions" ariaLabel={t('membership:kiosk_account_actions', '账户操作')} actions={[
      { key: 'topup', icon: 'squares-four', label: t('membership:api_topup', 'API充值'), onClick: () => setTab('topup') },
      { key: 'plans', icon: 'crown-simple', label: t('membership:kiosk_view_plans', '查看会员'), onClick: () => setTab('plans') },
    ]} />
  </aside>;

  return <div className="km-page" data-testid="kiosk-membership-page">
    <KioskPagebar backLabel={t('membership:kiosk_back_settings', '返回设置')} onBack={() => navigate('/kiosk/settings')} title={t('membership:kiosk_title', '会员与充值')} status={<span className={usable && !isTest ? 'km-header-ready' : 'km-header-status'} role="status">{headerState}</span>} action={{ icon: 'clock-counter-clockwise', label: t('membership:kiosk_order_history', '订单记录'), onClick: () => { setPurchase(null); void checkout.openHistory(); } }} />
    <nav className="km-tabs" role="tablist" aria-label={t('membership:kiosk_title', '会员与充值')}>{tabs.map(([key, label]) => <button key={key} type="button" id={`km-tab-${key}`} role="tab" aria-selected={tab === key} aria-controls={tab === key ? `km-panel-${key}` : undefined} tabIndex={tab === key ? 0 : -1} onClick={() => setTab(key)} onKeyDown={event => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      event.preventDefault();
      const next = tabs[(tabs.findIndex(([id]) => id === tab) + (event.key === 'ArrowRight' ? 1 : 2)) % tabs.length][0];
      setTab(next); document.getElementById(`km-tab-${next}`)?.focus();
    }}>{label}</button>)}</nav>
    <KioskScrollZone className="km-scroll" resetKey={tab}>
      <section className="km-body" id={`km-panel-${tab}`} role="tabpanel" aria-labelledby={`km-tab-${tab}`}>
        {tab === 'usage' && <div className="km-usage"><section className="km-resource">
          {!usable ? <div className="km-empty" role="status"><h2>{boundaryPending ? t('membership:kiosk_period_quota_pending', '周期额度待核对') : emptyTitle}</h2><p>{t('membership:kiosk_pending_no_order', '确认前不显示剩余比例，也不创建订单。')}</p><button type="button" className="km-primary" onClick={() => void refresh()} disabled={status === 'loading'}>{t('membership:kiosk_resync', '重新同步')}</button></div>
            : activePlan ? <>
              <div className="km-available"><span>{usage?.term?.remaining === 0 || usage?.week?.remaining === 0 ? t('membership:kiosk_api_when_insufficient', '会员额度不足时使用API积分') : t('membership:kiosk_member_first', '会员额度优先用于分析')}</span><InfoButton kind="quota" onOpen={setInfo} /></div>
              <UsageWindow kind="term" period={usage?.term ?? null} seconds={countdowns.term} />
              <UsageWindow kind="week" period={usage?.week ?? null} seconds={countdowns.week} />
              <p className="km-footnote">{t('membership:kiosk_usage_fallback', '两项剩余须同时足够本次分析；不足时整次使用API积分。')}<br />{t('membership:kiosk_result_reuse', '一次结果含领地与支招，重复查看不重复扣费。')}</p>
            </> : <section className="km-free"><KioskSecLabel zh={t('membership:kiosk_weekly_free_reports', '每周免费普通报告')} action={<InfoButton kind="quota" onOpen={setInfo} />} />
              {usage?.free?.eligible ? <><p className="km-free-count">{t('membership:kiosk_free_reports_remaining', '剩余 {remaining} / {limit} 份', { remaining: number(usage.free.remaining), limit: number(usage.free.limit) })}</p><p>{t('membership:kiosk_free_report_only', '普通报告资格，不赠通用分析额度')}</p><p>{t('membership:kiosk_week_reset_beijing', '周一零点重置 · 北京时间')}</p><p><Num>{countdown(countdowns.free)}</Num></p></>
                : <><h2>{t('membership:kiosk_free_pending', '免费报告资格待核验')}</h2><p>{t('membership:kiosk_free_verify_account', '请先完成账户验证，核验通过后显示本周资格。')}</p></>}
              <p className="km-footnote">{t('membership:kiosk_owned_result_reuse', '已拥有结果可反复查看；领地与支招含在同一结果内。')}</p>
            </section>}
        </section>{account}</div>}
        {tab === 'plans' && <section className="km-plans">
          <KioskSecLabel zh={t('membership:plans', '会员')} value={t('membership:kiosk_full_use_savings', '额度用满时，比API更省')} action={<InfoButton kind="quota" onOpen={setInfo} />} />
          {catalog ? <div className="km-plan-grid">{catalog.plans.map(plan => {
            const current = activePlan?.code === plan.code;
            const unavailable = !plan.sale_enabled;
            const enabled = paymentReady && catalog.capabilities.membership && usage?.capabilities.membership && catalog.membership_mode === 'enabled' && !unavailable;
            return <article key={plan.code} className={`km-plan${current ? ' is-current' : ''}${unavailable ? ' is-unavailable' : ''}`}>
              <div className="km-plan-head"><strong>{plan.name}</strong><span>{unavailable ? t('membership:kiosk_not_available', '暂未开放') : current ? t('membership:kiosk_current_plan', '当前会员') : ''}</span></div>
              <div className="km-plan-price"><Num>{money(plan.amount_fen)}</Num> <small>{t('membership:kiosk_plan_term', '/ {days}天', { days: number(plan.term_days) })}</small></div>
              <p className="km-saving">{t('membership:kiosk_save_vs_api', '比API约省 {percent}', { percent: number(plan.full_use_savings_percent / 100, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 }) })}</p>
              <div className="km-report-reference"><span>{t('membership:kiosk_term_reports', '普通报告 · {days}天共约{reports}盘', { days: number(plan.term_days), reports: number(plan.term_report_reference) })}</span><strong>{t('membership:kiosk_week_reports', '每周最多约 {reports} 盘', { reports: number(plan.week_report_reference) })}</strong></div>
              <button type="button" className={plan.code === 'pro' ? 'km-primary' : ''} disabled={!enabled || checkout.creating} onClick={() => buy(`membership_${plan.code}`, true)}>{unavailable ? t('membership:kiosk_not_available', '暂未开放') : current ? t('membership:kiosk_renew_plan', '续费 {plan}', { plan: plan.name }) : t('membership:kiosk_choose_plan', '选择 {plan}', { plan: plan.name })}</button>
            </article>;
          })}</div> : <div className="km-empty"><h2>{t('membership:kiosk_plan_catalog_pending', '会员目录待同步')}</h2><p>{t('membership:kiosk_plan_catalog_help', '目录确认后显示价格与权益。')}</p><button type="button" onClick={() => void refresh()}>{t('membership:kiosk_resync', '重新同步')}</button></div>}
          <div className="km-plan-footer"><p>{t('membership:kiosk_report_estimate', '按{moves}手估算，受本期剩余限制；高级约{multiplier}倍消耗', { moves: number(300), multiplier: multiplier === null ? '—' : number(multiplier) })}<br />{t('membership:kiosk_savings_condition', '优惠按本期额度用满计算；未用满时，实际优惠随用量变化')}</p>{paymentReason && <span role="status">{paymentReason}</span>}</div>
        </section>}
        {tab === 'topup' && <section className="km-topup"><article className="km-api-rates">
          <KioskSecLabel zh={t('membership:kiosk_api_pay_as_you_go', 'API充值 · 按用量付费')} action={<InfoButton kind="pricing" onOpen={setInfo} />} />
          <div className="km-rate"><span>{t('membership:kiosk_normal_analysis', '普通分析')}</span><strong>{t('membership:kiosk_points_per_move', '{points} 积分 / 手', { points: points(catalog?.profiles.normal.credits_per_position) })}</strong></div>
          <div className="km-rate"><span>{t('membership:kiosk_advanced_analysis', '高级分析')}</span><strong>{t('membership:kiosk_points_per_move', '{points} 积分 / 手', { points: points(catalog?.profiles.advanced.credits_per_position) })}</strong></div>
          <p className="km-report-quote">{t('membership:kiosk_normal_report_quote', '{moves}手报告 · 普通 {points} 积分', { moves: number(300), points: points(catalog ? 301 * catalog.profiles.normal.credits_per_position : null) })}<br />{t('membership:kiosk_advanced_report_quote', '高级 {points} 积分，均含初始局面', { points: points(catalog ? 301 * catalog.profiles.advanced.credits_per_position : null) })}</p>
          <p className="km-footnote">{t('membership:kiosk_topup_member_priority', '两项会员剩余足够时优先使用会员额度，否则整次使用API积分。')}<br />{t('membership:kiosk_no_auto_topup', '分析前确认来源与报价，不自动充值。')}</p>
          <div className="km-alternative"><span>{t('membership:kiosk_frequent_member_saves', '经常使用，会员可更省')}</span><button type="button" onClick={() => setTab('plans')}>{t('membership:kiosk_compare_plans', '比较会员')}</button></div>
        </article><aside className="km-recharge">
          <div className="km-recharge-balance"><span>{t('membership:kiosk_current_api_balance', '当前API余额')}</span><strong>{t('membership:kiosk_points_amount', '{points} 积分', { points: points(wallet?.credits) })}</strong></div>
          <p className="km-exchange">{selected && selected.amount_fen > 0 ? t('membership:kiosk_exchange_rate', '{amount} = {points}积分', { amount: money(100), points: number(selected.credits / selected.amount_fen, { maximumFractionDigits: 2 }) }) : t('membership:kiosk_topup_catalog_pending', '充值目录待同步')}</p>
          <div className="km-amounts" role="group" aria-label={t('membership:kiosk_select_topup', '选择API充值金额')}>{catalog?.topups.map(option => <button key={option.sku} type="button" aria-label={t('membership:kiosk_topup_option', '{amount} {points}积分', { amount: money(option.amount_fen), points: points(option.credits) })} aria-pressed={selected?.sku === option.sku} onClick={() => setSelectedSku(option.sku)}><strong><Num>{money(option.amount_fen)}</Num></strong><span>{t('membership:kiosk_topup_points', '{points}积分', { points: points(option.credits) })}</span></button>)}</div>
          <p className="km-selected">{t('membership:kiosk_credited_points', '到账 {points} 积分', { points: points(selected?.credits) })}</p>
          <button type="button" className="km-primary" disabled={!paymentReady || !selected || checkout.creating} onClick={() => selected && buy(selected.sku, false)}>{selected ? t('membership:kiosk_topup_amount', '充值 {amount}', { amount: money(selected.amount_fen) }) : t('membership:kiosk_topup', '充值')}</button>
          <p className="km-footnote" role="status">{paymentReason ?? (catalog?.payments_mode === 'mock' ? t('membership:kiosk_test_order', 'TEST模拟订单 · 不会真实收款') : t('membership:kiosk_check_order_amount', '付款前核对订单金额'))}</p>
        </aside></section>}
      </section>
    </KioskScrollZone>
    {info && <CanvasDialog title={info === 'quota' ? t('membership:kiosk_quota_help', '会员额度与优惠说明') : t('membership:kiosk_pricing_help', 'API计价说明')} onClose={() => setInfo(null)}><KioskScrollZone grow className="km-dialog-copy" resetKey={info}>{info === 'quota' ? quotaInfo : pricingInfo}</KioskScrollZone><footer className="km-dialog-actions"><button type="button" className="km-primary" onClick={() => setInfo(null)}>{t('membership:kiosk_understood', '知道了')}</button></footer></CanvasDialog>}
    {checkout.history && <CanvasDialog title={t('membership:kiosk_order_history', '订单记录')} onClose={checkout.close}>
      <KioskScrollZone grow className="km-order-history">
        {checkout.history.loading ? <p className="km-note" role="status">{t('membership:kiosk_syncing_orders', '正在同步订单…')}</p> : checkout.history.error ? <p className="km-note" role="status">{checkout.history.error}</p> : checkout.history.orders.length ? checkout.history.orders.map(order => <button key={order.id} type="button" className="km-history-row" aria-label={t('membership:kiosk_view_order', '查看订单 {id}', { id: order.id })} onClick={() => checkout.openOrder(order)}>
          <span><strong>{t('membership:kiosk_order_history_item', '{kind} · {date}', { kind: order.kind === 'membership' ? t('membership:kiosk_membership_purchase', '会员购买') : t('membership:api_topup', 'API充值'), date: date(order.created_at) })}</strong><span className="km-note"><Num>{order.id}</Num></span></span>
          <span><strong><Num>{money(order.amount_fen)}</Num></strong><span className="km-note">{({ pending: t('membership:order_pending', '等待付款'), paid: t('membership:order_paid', '已支付'), expired: t('membership:order_expired', '订单已过期'), failed: t('membership:order_failed', '订单未完成'), cancelled: t('membership:order_cancelled', '订单已取消'), refunded: t('membership:order_refunded', '已退款') })[order.status]}</span></span>
        </button>) : <p className="km-note">{t('membership:kiosk_no_orders', '暂无订单记录')}</p>}
      </KioskScrollZone>
      <footer className="km-dialog-actions"><button type="button" onClick={() => void checkout.openHistory()} disabled={checkout.history.loading}>{t('membership:kiosk_resync', '重新同步')}</button><button type="button" className="km-primary" onClick={checkout.close}>{t('membership:kiosk_back', '返回')}</button></footer>
    </CanvasDialog>}
    {(purchase || checkout.creating || checkout.order || checkout.error) && <CanvasDialog title={t('membership:kiosk_order_confirmation', '订单确认')} onClose={closeOrder}>
      <KioskScrollZone grow className="km-dialog-copy">
      {purchase && !checkout.order && <div className="km-order-summary"><strong>{purchase.name}</strong><strong><Num>{money(purchase.amount)}</Num></strong></div>}
      {checkout.order ? <OrderReceipt order={checkout.order} /> : <p className="km-order-state" role="status">{checkout.creating ? t('membership:kiosk_creating_order', '正在创建订单…') : t('membership:kiosk_order_unconfirmed', '订单待确认')}</p>}
      {checkout.error && <p className="km-note" role="status">{checkout.error}</p>}
      </KioskScrollZone>
      <footer className="km-dialog-actions">{checkout.order?.provider === 'wechat' && checkout.order.status === 'pending' && <button type="button" onClick={() => void checkout.cancel()} disabled={checkout.cancelling || checkout.order.cancel_requested}>{checkout.cancelling ? t('membership:wechat_cancelling', '正在取消…') : t('membership:wechat_cancel', '取消订单')}</button>}
      {checkout.canRetry && (checkout.error && !checkout.order || checkout.order?.provider === 'wechat' && checkout.order.status === 'pending' && !checkout.order.payment_url && !checkout.order.cancel_requested && Date.parse(checkout.order.expires_at) > Date.now()) && <button type="button" onClick={checkout.retry}>{t('membership:wechat_retry', '安全重试')}</button>}
      {purchase && !checkout.order && !checkout.error && <button type="button" className="km-primary" disabled={!paymentReady || checkout.creating} onClick={() => void checkout.create({ sku: purchase.sku, provider: 'wechat', idempotency_key: crypto.randomUUID() })}>{checkout.creating ? t('membership:kiosk_creating_order', '正在创建订单…') : t('membership:wechat_pay', '微信支付')}</button>}
      {checkout.error && !checkout.order && <button type="button" onClick={() => void checkout.openHistory()}>{t('membership:kiosk_order_history', '订单记录')}</button>}<button type="button" className="km-primary" onClick={closeOrder}>{checkout.order?.status === 'paid' ? t('membership:kiosk_return_usage', '返回用量') : t('membership:kiosk_return_selection', '返回选择')}</button></footer>
    </CanvasDialog>}
  </div>;
}
