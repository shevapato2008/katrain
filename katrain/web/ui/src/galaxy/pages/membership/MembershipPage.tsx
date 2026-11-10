import { useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { alpha } from "@mui/material/styles";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  LinearProgress,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useAuth } from "../../../context/AuthContext";
import { membershipApi } from "../../../api/membershipApi";
import {
  formatPoints,
  planReportCopy,
} from "../../../features/membership/presentation";
import { useMembershipI18n, type MembershipTranslate } from "../../../features/membership/useMembershipI18n";
import { WechatNativePayment } from "../../../features/membership/WechatNativePayment";
import { useMembership } from "../../../features/membership/useMembership";
import type {
  BillingOrder,
  MembershipCatalog,
  MembershipPeriod,
  MembershipPlan,
  MembershipProfile,
} from "../../../features/membership/types";
import ContentPageHeader from "../../components/layout/ContentPageHeader";
import LoginModal from "../../components/auth/LoginModal";
import {
  useMembershipCheckout,
  type PurchaseSelection,
} from "./useMembershipCheckout";

const cardSx = {
  p: { xs: 2, sm: 3 },
  border: "1px solid",
  borderColor: (theme: { palette: { primary: { light: string } } }) =>
    alpha(theme.palette.primary.light, 0.4),
  borderRadius: 2,
  minWidth: 0,
};
// Galaxy's primary color is a dark fill; text actions need a lighter foreground.
const readableActionsSx = {
  "& .MuiButton-text:not(.Mui-disabled), & .MuiButton-outlined:not(.Mui-disabled)": {
    color: "#b7d9c2",
  },
  "& .MuiButton-outlined:not(.Mui-disabled)": {
    borderColor: "rgba(183, 217, 194, 0.65)",
  },
};
const numberSx = { fontVariantNumeric: "tabular-nums" };
type DisplayNumber = ReturnType<typeof useMembershipI18n>["number"];
const points = (credits: number | null | undefined, number: DisplayNumber) =>
  formatPoints(credits) === "—" ? "—" : number(credits! / 100, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const savings = (percent: number, number: DisplayNumber) =>
  number(percent / 100, { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
const depthCopy = (catalog: MembershipCatalog | null, t: MembershipTranslate, number: DisplayNumber) => {
  if (!catalog || catalog.profiles.normal.credits_per_position <= 0)
    return t("membership:advanced_depth_rule", "高级报告按服务端分析深度消耗。");
  const ratio =
    catalog.profiles.advanced.credits_per_position /
    catalog.profiles.normal.credits_per_position;
  return t("membership:advanced_depth_ratio", "高级报告消耗约 {ratio} 倍。", { ratio: number(ratio, { maximumFractionDigits: 2 }) });
};
const orderStatus = (status: BillingOrder["status"], t: MembershipTranslate) =>
  ({
    pending: t("membership:order_pending", "等待付款"),
    paid: t("membership:order_paid", "已支付"),
    expired: t("membership:order_expired", "订单已过期"),
    failed: t("membership:order_failed", "订单未完成"),
    refunded: t("membership:order_refunded", "已退款"),
    cancelled: t("membership:order_cancelled", "订单已取消"),
  })[status];

function Quota({
  label,
  period,
  seconds,
  weekly,
}: {
  label: string;
  period: MembershipPeriod | null;
  seconds: number | null;
  weekly?: boolean;
}) {
  const { t, date, countdown, number } = useMembershipI18n();
  const value = period && Number.isFinite(period.percent) && period.percent >= 0 && period.percent <= 100 ? period.percent : null;
  const percent = value === null ? "—" : savings(value, number);
  return (
    <Box sx={{ py: 2.5, borderBottom: "1px solid", borderColor: "divider" }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="baseline"
        gap={2}
      >
        <Typography component="h3" variant="h6" sx={{ fontSize: 18 }}>
          {label}
        </Typography>
        <Typography variant="h4" sx={{ ...numberSx, fontWeight: 400 }}>
          {percent}
        </Typography>
      </Stack>
      {value !== null ? (
        <LinearProgress
          aria-label={label}
          aria-valuetext={t("membership:remaining_percent", "剩余 {percent}", { percent })}
          aria-valuenow={value}
          variant="determinate"
          value={value}
          sx={{
            height: 8,
            borderRadius: 1,
            my: 1.5,
            bgcolor: "action.selected",
            "& .MuiLinearProgress-bar": { bgcolor: "primary.light" },
          }}
        />
      ) : (
        <Typography color="text.secondary" sx={{ my: 1.5 }}>
          {t("membership:quota_pending", "额度待确认")}
        </Typography>
      )}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        gap={0.5}
      >
        <Typography variant="body2" color="text.secondary">
          {t("membership:used_and_reserved", "已用及分析中 {percent}", { percent: value === null ? "—" : savings(100 - value, number) })}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {seconds === 0
            ? t("membership:quota_refresh_pending", "正在确认最新额度")
            : seconds === null
              ? t("membership:time_pending", "时间待确认")
              : weekly
                ? t("membership:quota_recovers_in", "{time}后恢复", { time: countdown(seconds) })
                : t("membership:quota_expires_in", "{time}后到期", { time: countdown(seconds) })}
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        {weekly
          ? t("membership:weekly_reset_rule", "每周一 00:00（北京时间）恢复本周额度。")
          : t("membership:galaxy_term_reset_rule", "至 {date} 到期（北京时间）；周一恢复不增加本期额度。", { date: date(period?.reset_at, true) })}
      </Typography>
    </Box>
  );
}

function Rules({ catalog }: { catalog: MembershipCatalog | null }) {
  const { t, number } = useMembershipI18n();
  return (
    <Accordion
      disableGutters
      elevation={0}
      sx={{
        mt: 2,
        bgcolor: "transparent",
        "&:before": { display: "none" },
        borderTop: "1px solid",
        borderColor: "divider",
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{ px: 0, minHeight: 48 }}
      >
        <Typography>{t("membership:billing_rules", "会员与 API 计费规则")}</Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 0 }}>
        <Stack spacing={1.5} color="text.secondary">
          <Typography variant="body2">
            {t("membership:quota_dual_rule", "本期、本周分别按各自额度显示剩余比例，一次分析需同时满足两项剩余。分析中的预留计入已用，失败后归还。")}
            {' '}{depthCopy(catalog, t, number)}
          </Typography>
          <Typography variant="body2">
            {t("membership:billing_source_rule", "优先使用会员额度；任一项会员剩余不足以完成本次分析时，整次使用已有 API 积分，不拆分扣费来源。积分不足时需充值或等待额度恢复，不自动购买积分或扣人民币。")}
          </Typography>
          <Typography variant="body2">
            {t("membership:quote_and_owned_rule", "开始分析前展示服务端报价与扣费来源。账户或用量状态未确认时暂不可开始分析。重复查看已拥有的结果、切换领地与支招，不重复收费。")}
          </Typography>
          <Typography variant="body2">
            {t("membership:galaxy_report_estimate_rule", "按每盘 300 手、含初始局面估算，受本期剩余限制。")}
            {catalog?.plans.map((plan) => (
              <span key={plan.code}>{' '}
                {t("membership:term_report_reference", "{plan} 每{days}天本期普通报告参考约{reports}盘。", { plan: plan.name, days: number(plan.term_days), reports: number(plan.term_report_reference) })}
              </span>
            ))}
            {' '}{t("membership:galaxy_report_reset_rule", "每周一 00:00（北京时间）恢复本周额度；本期剩余到期结束。")}
          </Typography>
          <Typography variant="body2">
            {t("membership:renewal_rule", "续费在已有会员到期后顺延，不重置当前已用与预留；待付款日期仅为预计，最终生效区间以付款后的服务端回执为准。付费会员不叠加 Free 普通报告资格。")}
          </Typography>
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

function PlanCards({
  catalog,
  currentCode,
  canBuy,
  select,
}: {
  catalog: MembershipCatalog;
  currentCode?: string;
  canBuy: boolean;
  select: (plan: MembershipPlan) => void;
}) {
  const { t, money, number } = useMembershipI18n();
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: {
          xs: "minmax(0,1fr)",
          md: `repeat(${Math.min(catalog.plans.length, 3)}, minmax(0,1fr))`,
        },
        gap: 2,
      }}
    >
      {catalog.plans.map((plan) => (
        <Paper
          key={plan.code}
          variant="outlined"
          sx={{
            ...cardSx,
            p: 0,
            overflow: "hidden",
            bgcolor:
              plan.code === currentCode
                ? (theme) => alpha(theme.palette.primary.main, 0.18)
                : "background.paper",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Box sx={{ p: 2.5 }}>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              gap={1}
            >
              <Typography component="h3" variant="h5">
                {plan.name}
              </Typography>
              {!plan.sale_enabled ? (
                <Chip size="small" label={t("membership:unavailable", "暂未开放")} variant="outlined" />
              ) : plan.code === currentCode ? (
                <Chip
                  size="small"
                  label={t("membership:current_plan", "当前会员")}
                  color="success"
                  variant="outlined"
                />
              ) : null}
            </Stack>
            <Typography
              variant="h3"
              sx={{ ...numberSx, fontWeight: 400, mt: 1.5, fontSize: 36 }}
            >
              {money(plan.amount_fen)}
              <Typography
                component="span"
                color="text.secondary"
                sx={{ ml: 0.75, fontSize: 14 }}
              >
                {t("membership:plan_term", "/ {days} 天", { days: number(plan.term_days) })}
              </Typography>
            </Typography>
          </Box>
          <Box
            sx={{
              px: 2.5,
              py: 1.75,
              bgcolor: (theme) => alpha(theme.palette.primary.main, 0.22),
              borderTop: "1px solid",
              borderBottom: "1px solid",
              borderColor: "divider",
            }}
          >
            <Typography sx={{ fontSize: 23, ...numberSx }}>
              {t("membership:savings_vs_api", "比 API 约省 {percent}", { percent: savings(plan.full_use_savings_percent, number) })}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("membership:full_use_days", "按 {days} 天额度用满计算", { days: number(plan.term_days) })}
            </Typography>
          </Box>
          <Box sx={{ p: 2.5, flex: 1 }}>
            <Typography sx={{ fontSize: 17 }}>
              {planReportCopy(plan.week_report_reference, t, number)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t("membership:term_total_reports", "{days}天共约{reports}盘", { days: number(plan.term_days), reports: number(plan.term_report_reference) })}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {t("membership:report_estimate_limit", "按每盘 300 手估算，受本期剩余限制。")}{' '}{depthCopy(catalog, t, number)}
            </Typography>
          </Box>
          <Box sx={{ p: 2.5, pt: 0 }}>
            <Button
              fullWidth
              variant={plan.code === currentCode ? "contained" : "outlined"}
              disabled={!canBuy || !plan.sale_enabled}
              onClick={() => select(plan)}
              aria-label={
                !plan.sale_enabled
                  ? t("membership:plan_unavailable", "{plan} 暂未开放", { plan: plan.name })
                  : plan.code === currentCode
                    ? t("membership:renew_plan", "续费 {plan}", { plan: plan.name })
                    : t("membership:select_plan", "选择 {plan}", { plan: plan.name })
              }
            >
              {!plan.sale_enabled
                ? t("membership:unavailable", "暂未开放")
                : plan.code === currentCode
                  ? t("membership:renew_plan", "续费 {plan}", { plan: plan.name })
                  : t("membership:select_plan", "选择 {plan}", { plan: plan.name })}
            </Button>
          </Box>
        </Paper>
      ))}
    </Box>
  );
}

export default function MembershipPage() {
  const { t, money, date, countdown, number } = useMembershipI18n();
  const auth = useAuth();
  const { catalog, usage, status, refresh, countdowns } = useMembership();
  const [params, setParams] = useSearchParams();
  const tab = ["usage", "recharge", "plans"].includes(params.get("tab") ?? "")
    ? params.get("tab")!
    : "usage";
  const setTab = (next: string) => {
    const updated = new URLSearchParams(params);
    updated.set("tab", next);
    setParams(updated);
  };
  const [loginOpen, setLoginOpen] = useState(false);
  const [profile, setProfile] = useState<MembershipProfile>("normal");
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const scope = JSON.stringify([
    auth.identityKey,
    auth.status,
    catalog?.environment ?? null,
  ]);
  const authenticated =
    auth.status === "authenticated" && auth.identityKey !== null;
  const { checkout, select, openOrder, close, create, cancel } = useMembershipCheckout(
    scope,
    authenticated,
    auth.token,
  );
  const [history, setHistory] = useState<{
    scope: string;
    orders: BillingOrder[];
    status: "loading" | "ready" | "error";
  } | null>(null);
  const historyRef = useRef<AbortController | null>(null);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  useEffect(() => {
    setHistory(null);
    historyRef.current?.abort();
    return () => {
      historyRef.current?.abort();
    };
  }, [scope]);
  const ready = authenticated && status === "ready" && !!catalog && !!usage;
  const stale = status === "error" && !!usage;
  const verifiedUsage = !!usage && usage.capabilities.usage && (ready || stale);
  const mode = catalog?.payments_mode;
  const ordersEnabled =
    ready && catalog.capabilities.orders && usage.capabilities.orders;
  const safePaymentMode =
    (mode === "mock" && catalog?.environment.toLowerCase() === "test") || mode === "live";
  const canPay =
    ordersEnabled && safePaymentMode && usage.payments_mode === mode;
  const canBuyMembership =
    !!canPay &&
    !!catalog?.capabilities.membership &&
    !!usage?.capabilities.membership;
  const paymentNotice = !ready
    ? t("membership:payment_account_pending", "账户与用量确认后，才能创建付款订单。")
    : !canPay
      ? t("membership:payments_unavailable", "支付暂未开放，当前不能创建付款订单。")
      : null;
  const topup =
    catalog?.topups.find((item) => item.sku === selectedSku) ??
    catalog?.topups.find((item) => item.sku === "topup_30") ??
    catalog?.topups[0];
  const choosePlan = (plan: MembershipPlan) => {
    if (!catalog || !canBuyMembership || !plan.sale_enabled) return;
    select({
      sku: `membership_${plan.code}`,
      planName: plan.name,
      termDays: plan.term_days,
      kind: "membership",
      amountFen: plan.amount_fen,
      catalogVersion: catalog.catalog_version,
      weekReportReference: plan.week_report_reference,
    });
  };
  const chooseTopup = () => {
    if (
      !catalog ||
      !canPay ||
      !topup ||
      !["topup_10", "topup_30", "topup_100"].includes(topup.sku)
    )
      return;
    select({
      sku: topup.sku as PurchaseSelection["sku"],
      credits: topup.credits,
      kind: "topup",
      amountFen: topup.amount_fen,
      catalogVersion: catalog.catalog_version,
    });
  };
  const loadHistory = async () => {
    if (
      !authenticated ||
      !catalog || !usage || catalog.environment !== usage.environment
    )
      return;
    historyRef.current?.abort();
    const controller = new AbortController();
    historyRef.current = controller;
    setHistory({ scope, orders: [], status: "loading" });
    try {
      const result = await membershipApi.getOrders(
        auth.token,
        controller.signal,
      );
      if (!controller.signal.aborted && scopeRef.current === scope)
        setHistory({ scope, orders: result.orders, status: "ready" });
    } catch {
      if (!controller.signal.aborted && scopeRef.current === scope)
        setHistory({ scope, orders: [], status: "error" });
    } finally {
      if (historyRef.current === controller) historyRef.current = null;
    }
  };
  const titleStatus =
    status === "ready"
      ? t("membership:synced", "已同步")
      : stale
        ? t("membership:stale", "待更新")
        : status === "loading"
          ? t("membership:confirming", "正在确认")
          : status === "unavailable"
            ? t("membership:temporarily_unavailable", "暂不可用")
            : t("membership:date_pending", "待确认");
  const currentPlan = verifiedUsage ? usage.plan.current : null;
  const wallet = verifiedUsage ? points(usage.wallet?.credits, number) : "—";
  const normal = catalog?.profiles.normal,
    advanced = catalog?.profiles.advanced;
  const rate = catalog?.profiles[profile];
  const currentHistory = history?.scope === scope ? history : null;
  let body: ReactNode;

  if (auth.status !== "authenticated") {
    body = (
      <Paper variant="outlined" sx={cardSx}>
        <Typography variant="h5" sx={{ mb: 2 }}>
          {auth.status === "checking"
            ? t("membership:account_checking", "正在确认账户")
            : auth.status === "unavailable"
              ? t("membership:account_unconfirmed", "账户状态暂未确认")
              : t("membership:login_to_view", "登录后查看会员与用量")}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {t("membership:account_identity_help", "确认账户身份后，显示会员权益、Free 资格与 API 积分余额。")}
        </Typography>
        {auth.status === "checking" ? (
          <CircularProgress size={24} aria-label={t("membership:account_checking", "正在确认账户")} />
        ) : auth.status === "unavailable" ? (
          <Button variant="outlined" onClick={() => void auth.retry()}>
            {t("membership:account_retry", "重试账户验证")}
          </Button>
        ) : (
          <Button variant="contained" onClick={() => setLoginOpen(true)}>
            {t("membership:login", "登录账户")}
          </Button>
        )}
      </Paper>
    );
  } else if (!catalog || !usage) {
    body = (
      <Paper variant="outlined" sx={cardSx}>
        {status === "loading" ? (
          <Stack direction="row" gap={2} alignItems="center">
            <CircularProgress size={24} />
            <Typography>{t("membership:loading", "正在读取会员与用量…")}</Typography>
          </Stack>
        ) : (
          <>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {t("membership:unavailable_title", "会员与用量暂不可用")}
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              {t("membership:unconfirmed_help", "账户权益与余额尚未确认，请稍后重试。")}
            </Typography>
            <Button variant="outlined" onClick={() => void refresh()}>
              {t("membership:reload", "重新载入")}
            </Button>
          </>
        )}
      </Paper>
    );
  } else if (tab === "usage") {
    body = (
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "minmax(0,1fr)",
            lg: "minmax(0,1fr) 290px",
          },
          gap: 2.5,
        }}
      >
        <Paper variant="outlined" sx={cardSx}>
          {currentPlan ? (
            <>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                justifyContent="space-between"
                alignItems={{ sm: "center" }}
                gap={1}
              >
                <Typography component="h2" variant="h5">
                  {t("membership:quota", "会员额度")}
                </Typography>
                <Chip
                  label={stale ? t("membership:source_pending", "扣费来源待确认") : t("membership:membership_first", "优先使用会员额度")}
                  variant="outlined"
                  size="small"
                />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {t("membership:whole_request_fallback", "会员不足以完成本次分析时，整次使用已有 API 积分。")}
              </Typography>
              <Quota
                label={t("membership:term_remaining", "本期剩余")}
                period={verifiedUsage ? usage.term : null}
                seconds={countdowns.term}
              />
              <Quota
                label={t("membership:week_remaining", "本周剩余")}
                period={verifiedUsage ? usage.week : null}
                seconds={countdowns.week}
                weekly
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                {t("membership:quota_reservation_help", "两项剩余分别计算，一次分析需同时满足。分析中的预留已计入使用比例，失败后归还。")}
              </Typography>
            </>
          ) : !verifiedUsage ? (
            <>
              <Typography component="h2" variant="h5" sx={{ mb: 2 }}>
                {t("membership:entitlement_pending", "账户权益待确认")}
              </Typography>
              <Typography color="text.secondary">
                {t("membership:membership_free_pending_help", "会员与 Free 资格尚未确认，请重新载入后查看。")}
              </Typography>
            </>
          ) : (
            <>
              <Typography component="h2" variant="h5" sx={{ mb: 2 }}>
                {t("membership:free_weekly_title", "Free · 本周普通报告资格")}
              </Typography>
              {verifiedUsage &&
              usage.capabilities.can_claim_free_report &&
              usage.free?.eligible ? (
                <>
                  <Typography variant="h4" sx={{ mb: 2 }}>
                    {t("membership:free_remaining", "本周剩余 {count} 份", { count: number(usage.free.remaining) })}
                  </Typography>
                  <Typography color="text.secondary">
                    {t("membership:free_eligibility_rule", "每自然周 {count} 份普通报告的独立领取资格；需满足身份验证条件，不作为通用分析额度。", { count: number(usage.free.limit) })}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 2 }}
                  >
                    {countdowns.free === null || countdowns.free === 0
                      ? countdown(countdowns.free)
                      : t("membership:free_reset_countdown", "{time}后恢复 · {date}（北京时间）", { time: countdown(countdowns.free), date: date(usage.free.reset_at, true) })}
                  </Typography>
                </>
              ) : (
                <>
                  <Typography variant="h6" sx={{ mb: 1 }}>
                    {verifiedUsage && usage.free && !usage.free.eligible
                      ? t("membership:free_unavailable", "Free 资格当前不可用")
                      : t("membership:free_pending", "Free 资格待确认")}
                  </Typography>
                  <Typography color="text.secondary">
                    {t("membership:free_unavailable_rule", "Free 普通报告需先满足可信身份条件。当前不提供可领取数量，付费会员不叠加 Free 报告资格。")}
                  </Typography>
                </>
              )}
              <Button sx={{ mt: 2 }} onClick={() => setTab("plans")}>
                {t("membership:compare_membership_api", "比较会员与 API")}
              </Button>
            </>
          )}
        </Paper>
        <Stack gap={2.5}>
          <Paper variant="outlined" sx={cardSx}>
            <Typography color="text.secondary" variant="body2">
              {t("membership:current_plan", "当前会员")}
            </Typography>
            <Typography variant="h4" sx={{ mt: 1, mb: 1.5 }}>
              {verifiedUsage ? (currentPlan?.name ?? "Free") : t("membership:date_pending", "待确认")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {currentPlan
                ? t("membership:valid_until", "有效期至 {date}（北京时间）", { date: date(currentPlan.ends_at, true) })
                : verifiedUsage
                  ? t("membership:free_weekly_eligibility", "每自然周的独立普通报告资格")
                  : t("membership:plan_pending", "会员权益待确认")}
            </Typography>
            {verifiedUsage && usage.plan.next && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                {t("membership:next_membership", "已购 {plan} · {date} 生效", { plan: usage.plan.next.name, date: date(usage.plan.next.starts_at, true) })}
              </Typography>
            )}
            <Button
              fullWidth
              variant="outlined"
              sx={{ mt: 2 }}
              onClick={() => setTab("plans")}
            >
              {t("membership:view_plans", "查看会员方案")}
            </Button>
          </Paper>
          <Paper variant="outlined" sx={cardSx}>
            <Typography color="text.secondary" variant="body2">
              {t("membership:api_balance", "API 积分余额")}
            </Typography>
            <Typography variant="h4" sx={{ my: 1, ...numberSx }}>
              {wallet}
              <Typography
                component="span"
                color="text.secondary"
                sx={{ fontSize: 15, ml: 1 }}
              >
                {t("membership:points", "积分")}
              </Typography>
            </Typography>
            <Typography color="text.secondary" variant="body2">
              {t("membership:points_exchange_rate", "1 元 = 1 积分")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("membership:normal_position_cost", "普通约 {points} 积分/手", { points: normal ? points(normal.credits_per_position, number) : "—" })}
              <br />
              {t("membership:advanced_position_cost", "高级约 {points} 积分/手", { points: advanced ? points(advanced.credits_per_position, number) : "—" })}
            </Typography>
            <Button
              fullWidth
              variant="outlined"
              sx={{ mt: 2 }}
              onClick={() => setTab("recharge")}
            >
              {t("membership:api_topup", "API充值")}
            </Button>
          </Paper>
        </Stack>
      </Box>
    );
  } else if (tab === "plans") {
    body = (
      <>
        <Typography component="h2" variant="h5" sx={{ mb: 1 }}>
          {t("membership:galaxy_choose_membership", "按你的用量，选择会员")}
        </Typography>
        <Typography color="text.secondary" variant="body2" sx={{ mb: 2.5 }}>
          {t("membership:full_use_savings_rule", "按本期额度用满计算优惠；实际优惠随用量变化。续费在已有会员到期后顺延。")}
        </Typography>
        <PlanCards
          catalog={catalog}
          currentCode={currentPlan?.code}
          canBuy={canBuyMembership}
          select={choosePlan}
        />
        <Stack
          direction={{ xs: "column", sm: "row" }}
          alignItems={{ sm: "center" }}
          justifyContent="space-between"
          gap={2}
          sx={{ mt: 3 }}
        >
          <Box>
            <Typography variant="h6">{t("membership:galaxy_occasional_analysis", "偶尔分析，也可以按需充值")}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t("membership:galaxy_api_help", "API 无需订阅，1 元 = 1 积分。分析开始前确认服务端报价。")}
            </Typography>
          </Box>
          <Button variant="outlined" onClick={() => setTab("recharge")}>
            {t("membership:view_api_topup", "查看 API 充值")}
          </Button>
        </Stack>
      </>
    );
  } else {
    body = (
      <>
        <Paper
          variant="outlined"
          sx={{
            ...cardSx,
            p: 0,
            overflow: "hidden",
            mb: 2.5,
            display: "grid",
            gridTemplateColumns: {
              xs: "minmax(0,1fr)",
              md: "minmax(0,1fr) 300px",
            },
          }}
        >
          <Box sx={{ p: { xs: 2, sm: 3 }, minWidth: 0 }}>
            <Typography component="h2" variant="h5">
              {t("membership:api_on_demand", "API 按需分析")}
            </Typography>
            <Table
              size="small"
              aria-label={t("membership:api_prices", "API 分析价格")}
              sx={{
                mt: 1,
                "& th, & td": { px: 0, py: 1.5 },
                "& td": { fontSize: 16 },
              }}
            >
              <TableHead>
                <TableRow>
                  <TableCell>{t("membership:analysis_depth", "分析深度")}</TableCell>
                  <TableCell align="right">{t("membership:position_cost", "每手费用")}</TableCell>
                  <TableCell align="right">{t("membership:compute", "计算量")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(["normal", "advanced"] as const).map((key) => (
                  <TableRow key={key}>
                    <TableCell>{key === "normal" ? t("membership:normal", "普通") : t("membership:advanced", "高级")}</TableCell>
                    <TableCell align="right">
                      <Typography
                        component="span"
                        sx={{ fontSize: 24, ...numberSx }}
                      >
                        {points(catalog.profiles[key].credits_per_position, number)}
                      </Typography>{" "}
                      <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                      >
                        {t("membership:points", "积分")}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {t("membership:visits", "{count} 次访问", { count: number(catalog.profiles[key].visits) })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {t("membership:position_pricing_rule", "单局面与整盘使用相同单价；整盘按手数加初始局面计费。")}
            </Typography>
          </Box>
          <Box
            sx={{ p: { xs: 2, sm: 3 }, bgcolor: "#eae2cd", color: "#223729" }}
          >
            <Typography variant="body2">{t("membership:galaxy_report_example_title", "一盘 300 手，花费多少？")}</Typography>
            <ToggleButtonGroup
              value={profile}
              exclusive
              size="small"
              onChange={(_, value: MembershipProfile | null) =>
                value && setProfile(value)
              }
              aria-label={t("membership:example_depth", "示例分析深度")}
              sx={{
                my: 1.5,
                "& button": {
                  minHeight: 44,
                  color: "#304936",
                  borderColor: "#aeb7a1",
                  "&.Mui-selected": { bgcolor: "#fff8e8", color: "#223729" },
                },
              }}
            >
              <ToggleButton value="normal">{t("membership:normal", "普通")}</ToggleButton>
              <ToggleButton value="advanced">{t("membership:advanced", "高级")}</ToggleButton>
            </ToggleButtonGroup>
            <Typography variant="h3" sx={{ fontSize: 36, mb: 1, color: "inherit", ...numberSx }}>
              {rate ? points(rate.credits_per_position * 301, number) : "—"}
              <Typography component="span" sx={{ fontSize: 16, ml: 1 }}>
                {t("membership:points", "积分")}
              </Typography>
            </Typography>
            <Typography variant="body2">
              {t("membership:report_example_rule", "含初始局面，共 301 个分析局面。实际费用以提交前服务端报价为准。")}
            </Typography>
          </Box>
        </Paper>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "minmax(0,1fr)",
              lg: "minmax(0,1.2fr) minmax(0,1fr)",
            },
            gap: 2.5,
          }}
        >
          <Paper variant="outlined" sx={cardSx}>
            <Stack
              direction="row"
              justifyContent="space-between"
              gap={2}
              alignItems="center"
            >
              <Box>
                <Typography variant="body2" color="text.secondary">
                  {t("membership:api_balance", "API 积分余额")}
                </Typography>
                <Typography variant="h4" sx={{ mt: 0.5, ...numberSx }}>
                  {wallet}
                  <Typography component="span" sx={{ fontSize: 15, ml: 1 }}>
                    {t("membership:points", "积分")}
                  </Typography>
                </Typography>
              </Box>
              <Typography color="text.secondary" variant="body2">
                {t("membership:points_exchange_rate", "1 元 = 1 积分")}
                <br />
                {t("membership:on_demand_no_subscription", "按需购买，无需订阅")}
              </Typography>
            </Stack>
            <Divider sx={{ my: 2.5 }} />
            <Typography component="h2" variant="h6">
              {t("membership:choose_topup", "选择充值金额")}
            </Typography>
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: "repeat(3,minmax(0,1fr))",
                gap: 1,
                mt: 1.5,
              }}
            >
              {catalog.topups.map((item) => (
                <Button
                  key={item.sku}
                  variant={item.sku === topup?.sku ? "contained" : "outlined"}
                  aria-pressed={item.sku === topup?.sku}
                  onClick={() => setSelectedSku(item.sku)}
                  aria-label={t("membership:topup_option", "{amount}，到账 {points} 积分", { amount: money(item.amount_fen), points: points(item.credits, number) })}
                  sx={{
                    flexDirection: "column",
                    alignItems: "flex-start",
                    py: 1.5,
                    px: { xs: 1, sm: 1.5 },
                    minWidth: 0,
                  }}
                >
                  <Typography
                    component="span"
                    sx={{ fontSize: { xs: 18, sm: 25 }, maxWidth: "100%", whiteSpace: "nowrap", ...numberSx }}
                  >
                    {money(item.amount_fen)}
                  </Typography>
                  <Typography
                    component="span"
                    sx={{ fontSize: { xs: 12, sm: 14 }, overflowWrap: "anywhere" }}
                  >
                    {t("membership:points_amount", "{points} 积分", { points: points(item.credits, number) })}
                  </Typography>
                </Button>
              ))}
            </Box>
            <Button
              fullWidth
              variant="contained"
              size="large"
              sx={{ mt: 2.5 }}
              disabled={!canPay || !topup}
              onClick={chooseTopup}
            >
              {t("membership:topup_amount", "充值 {amount}", { amount: topup ? money(topup.amount_fen) : "—" })}
            </Button>
            <Typography color="text.secondary" variant="body2" sx={{ mt: 1.5 }}>
              {t("membership:topup_arrival_rule", "付款确认后到账。会员不足时使用已有 API 积分，不自动充值。")}
            </Typography>
          </Paper>
          <Paper variant="outlined" sx={cardSx}>
            <Typography component="h2" variant="h5">
              {t("membership:galaxy_membership_savings", "常用分析，会员更省")}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {t("membership:galaxy_comparison_basis", "同等普通分析量，按本期额度用满计算。")}
            </Typography>
            <Stack divider={<Divider />} sx={{ mt: 1 }}>
              {catalog.plans.map((plan) => (
                <Stack
                  key={plan.code}
                  direction="row"
                  justifyContent="space-between"
                  gap={1}
                  sx={{ py: 1.5 }}
                >
                  <Box>
                    <Typography>
                      {t("membership:galaxy_plan_price", "{plan} · {amount} / {days} 天", { plan: plan.name, amount: money(plan.amount_fen), days: number(plan.term_days) })}
                    </Typography>
                    <Typography color="text.secondary" variant="body2">
                      {plan.sale_enabled
                        ? t("membership:weekly_reports", "每周最多约 {reports} 盘", { reports: number(plan.week_report_reference) })
                        : t("membership:weekly_reports_unavailable", "每周最多约 {reports} 盘 · 暂未开放", { reports: number(plan.week_report_reference) })}
                    </Typography>
                  </Box>
                  <Typography sx={{ whiteSpace: "nowrap" }}>
                    {t("membership:savings_approx", "约省 {percent}", { percent: savings(plan.full_use_savings_percent, number) })}
                  </Typography>
                </Stack>
              ))}
            </Stack>
            <Typography color="text.secondary" variant="body2" sx={{ mt: 1 }}>
              {t("membership:report_estimate_limit", "按每盘 300 手估算，受本期剩余限制。")}{' '}{depthCopy(catalog, t, number)}
            </Typography>
            <Button sx={{ mt: 1 }} onClick={() => setTab("plans")}>
              {t("membership:compare_plans", "比较会员方案")}
            </Button>
          </Paper>
        </Box>
      </>
    );
  }

  const order = checkout?.order;
  const selection = checkout?.selection;
  const confirmedSelection =
    selection && catalog?.catalog_version === selection.catalogVersion;
  return (
    <Box
      data-testid="membership-page"
      sx={{
        ...readableActionsSx,
        width: "100%",
        maxWidth: 1340,
        mx: "auto",
        p: { xs: 2, sm: 3, lg: 4 },
        pb: { xs: "calc(88px + env(safe-area-inset-bottom))", md: 4 },
        boxSizing: "border-box",
      }}
    >
      <ContentPageHeader
        title={t("membership:galaxy_title", "会员与用量")}
        status={<Chip size="small" variant="outlined" label={titleStatus} />}
      />
      <Stack
        direction={{ xs: "column", sm: "row" }}
        gap={1}
        alignItems={{ xs: "stretch", sm: "center" }}
        justifyContent="space-between"
        sx={{ mt: 1, mb: 2 }}
      >
        <Typography color="text.secondary" variant="body2" sx={{ minWidth: 0 }}>
          {t("membership:galaxy_intro", "查看分析用量，选择按需充值或会员。")}
        </Typography>
        {authenticated && (
          <Button
            size="small"
            startIcon={<RefreshIcon />}
            onClick={() => void refresh()}
            sx={{ whiteSpace: "nowrap", minHeight: 44, flexShrink: 0, alignSelf: { xs: "flex-end", sm: "auto" } }}
          >
            {t("membership:refresh", "刷新")}
          </Button>
        )}
      </Stack>
      <Tabs
        value={tab}
        onChange={(_, next: string) => setTab(next)}
        aria-label={t("membership:galaxy_tabs", "会员页面")}
        variant="scrollable"
        scrollButtons="auto"
        allowScrollButtonsMobile
        sx={{
          mb: 3,
          borderBottom: "1px solid",
          borderColor: "divider",
          "& .MuiTab-root": { fontSize: 18, minHeight: 48 },
          "& .MuiTab-root.Mui-selected": { color: "#b7d9c2" },
          "& .MuiTabs-indicator": { bgcolor: "#b7d9c2" },
        }}
      >
        <Tab value="usage" label={t("membership:usage", "用量")} />
        <Tab value="recharge" label={t("membership:api_topup", "API充值")} />
        <Tab value="plans" label={t("membership:plans", "会员")} />
      </Tabs>
      {stale && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {t("membership:stale_warning", "当前显示上次载入的数据；账户与扣费来源待重新确认，购买暂不可用。")}
        </Alert>
      )}
      {status === "unavailable" && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {t("membership:service_unavailable", "当前服务未开放会员用量，权益与余额待确认。")}
        </Alert>
      )}
      {authenticated && catalog && tab !== "usage" && paymentNotice && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {paymentNotice}
        </Alert>
      )}
      {body}
      {authenticated && catalog && usage && (
        <>
          <Rules catalog={catalog} />
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            gap={2}
            sx={{ mt: 1 }}
          >
            <Typography variant="body2" color="text.secondary">
              {t("membership:server_authority", "余额与权益以服务端确认结果为准。")}
            </Typography>
            <Button
              onClick={() => void loadHistory()}
              disabled={
                !authenticated || catalog.environment !== usage.environment
              }
            >
              {t("membership:order_history", "订单记录")}
            </Button>
          </Stack>
          {currentHistory && (
            <Paper variant="outlined" sx={{ ...cardSx, mt: 2 }}>
              <Typography variant="h6" sx={{ mb: 1.5 }}>
                {t("membership:order_history", "订单记录")}
              </Typography>
              {currentHistory.status === "loading" ? (
                <CircularProgress size={24} />
              ) : currentHistory.status === "error" ? (
                <Alert
                  severity="warning"
                  action={
                    <Button onClick={() => void loadHistory()}>{t("membership:retry", "重试")}</Button>
                  }
                >
                  {t("membership:history_unavailable", "订单记录暂不可用")}
                </Alert>
              ) : !currentHistory.orders.length ? (
                <Typography color="text.secondary">{t("membership:no_orders", "暂无订单")}</Typography>
              ) : (
                <Stack divider={<Divider />}>
                  {currentHistory.orders.map((item) => (
                    <Button
                      key={item.id}
                      onClick={() => openOrder(item)}
                      sx={{
                        justifyContent: "space-between",
                        py: 1.5,
                        gap: 2,
                        textAlign: "left",
                      }}
                    >
                      <Box sx={{ minWidth: 0 }}>
                        <Typography>
                          {item.kind === "topup" ? t("membership:order_topup", "API 积分充值") : t("membership:membership_order", "会员订单")}{" "}
                          · {money(item.amount_fen)}
                        </Typography>
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ overflowWrap: "anywhere" }}
                        >
                          {item.id}
                        </Typography>
                      </Box>
                      <Typography sx={{ whiteSpace: "nowrap" }}>
                        {orderStatus(item.status, t)}
                      </Typography>
                    </Button>
                  ))}
                </Stack>
              )}
            </Paper>
          )}
        </>
      )}
      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} />
      {checkout && (
        <Dialog
          open
          onClose={close}
          fullWidth
          maxWidth="sm"
          aria-labelledby="membership-checkout-title"
          sx={readableActionsSx}
        >
          <DialogTitle id="membership-checkout-title">
            {order ? orderStatus(order.status, t) : t("membership:confirm_purchase", "确认购买")}
          </DialogTitle>
          <DialogContent>
            {(order?.payments_mode === "mock" ||
              (!order && mode === "mock")) && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {t("membership:test_order_warning", "TEST 模拟订单，不会真实收款")}
              </Alert>
            )}
            <Typography variant="h6">
              {selection?.kind === "membership"
                ? t("membership:galaxy_plan_selection", "{plan} · {days} 天会员", { plan: selection.planName, days: number(selection.termDays) })
                : selection?.kind === "topup" || order?.kind === "topup"
                  ? t("membership:order_topup", "API 积分充值")
                  : t("membership:membership_order", "会员订单")}
            </Typography>
            <Typography
              variant="h3"
              sx={{ fontSize: 36, mt: 1.5, mb: 2, ...numberSx }}
            >
              {money(order?.amount_fen ?? selection?.amountFen ?? 0)}
            </Typography>
            {selection && (
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                {selection.kind === "membership"
                  ? planReportCopy(selection.weekReportReference, t, number)
                  : t("membership:topup_arrival", "到账 {points} 积分", { points: points(selection.credits, number) })}
              </Typography>
            )}
            {!order && mode === "live" && <Typography className="wechat-native-before-payment" variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t("membership:wechat_another_screen", "手机浏览时，请在另一块屏幕打开本页，再用手机微信扫码。")}
            </Typography>}
            {!order && selection?.kind === "membership" && (
              <Typography variant="body2" color="text.secondary">
                {t("membership:checkout_renewal_rule", "在已有会员到期后顺延，不重置当前额度。生效日期以付款后的服务端回执为准。")}
              </Typography>
            )}
            {order && (
              <>
                <Typography variant="body2" color="text.secondary">
                  {t("membership:order_id", "订单编号")}
                </Typography>
                <Typography sx={{ overflowWrap: "anywhere", mb: 2 }}>
                  {order.id}
                </Typography>
                {order.provider === "wechat" ? <WechatNativePayment order={order} /> : <Alert
                  severity={
                    order.status === "paid"
                      ? "success"
                      : ["failed", "expired"].includes(order.status)
                        ? "warning"
                        : "info"
                  }
                >
                  {order.status === "pending"
                    ? t("membership:pending_order_notice", "等待付款，页面将自动确认服务端状态。")
                    : orderStatus(order.status, t)}
                </Alert>}
                {order.status === "pending" && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 1.5 }}
                  >
                    {t("membership:order_expires_at", "订单有效期至 {date}（北京时间）。", { date: date(order.expires_at, true) })}
                    {order.estimated_starts_at && t("membership:order_estimated_dates", "预计生效 {start}，预计到期 {end}（北京时间）；最终日期以付款回执为准。", { start: date(order.estimated_starts_at, true), end: date(order.estimated_ends_at, true) })}
                  </Typography>
                )}
                {order.status === "paid" && order.fulfillment && (
                  <Box sx={{ mt: 2 }}>
                    {order.kind === "topup" ? (
                      <Typography>
                        {t("membership:order_actual_points", "实际到账 {points} 积分", { points: points(order.fulfillment.credits, number) })}
                      </Typography>
                    ) : (
                      <Typography>
                        {t("membership:order_actual_start", "实际生效 {date}（北京时间）", { date: date(order.fulfillment.starts_at, true) })}
                        <br />
                        {t("membership:order_actual_end", "实际到期 {date}（北京时间）", { date: date(order.fulfillment.ends_at, true) })}
                      </Typography>
                    )}
                  </Box>
                )}
                {order.status === "paid" && !order.fulfillment && (
                  <Typography color="text.secondary" sx={{ mt: 2 }}>
                    {t("membership:fulfillment_pending", "权益回执待确认，请刷新用量查看。")}
                  </Typography>
                )}
                {order.status === "pending" && order.provider === "live" && (
                  <Typography color="text.secondary" sx={{ mt: 2 }}>
                    {t("membership:payment_channel_unavailable", "支付渠道接入尚未开放，请勿在页面外向未知账户付款。")}
                  </Typography>
                )}
              </>
            )}
            {checkout?.error && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                {checkout.error === "result_unknown"
                  ? t("membership:order_result_unknown", "订单结果暂未确认，请先查看订单记录，避免重复创建。")
                  : t("membership:order_poll_error", "暂时无法确认付款状态，正在重试。请勿重复付款。")}
              </Alert>
            )}
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2, flexWrap: "wrap", gap: 1, "& .MuiButton-root": { minHeight: 44 } }}>
            <Button onClick={close}>
              {order?.status === "paid" ? t("membership:done", "完成") : t("membership:close", "关闭")}
            </Button>
            {order?.provider === "wechat" && order.status === "pending" && <Button onClick={() => void cancel()} disabled={checkout.busy || order.cancel_requested}>{checkout.cancelling ? t("membership:wechat_cancelling", "正在取消…") : t("membership:wechat_cancel", "取消订单")}</Button>}
            {(!order || order.provider === "wechat" && !order.payment_url && !order.cancel_requested && order.status === "pending" && Date.parse(order.expires_at) > Date.now() && selection) && (
              <Button
                variant="contained"
                disabled={
                  !canPay ||
                  !confirmedSelection ||
                  checkout?.busy
                }
                onClick={() => {
                  if (
                    canPay &&
                    confirmedSelection &&
                    (mode === "mock" || mode === "live")
                  )
                    void create(mode === "live" ? "wechat" : "mock");
                }}
              >
                {checkout?.busy ? t("membership:creating_order", "正在创建…") : checkout.error || order ? t("membership:wechat_retry", "安全重试") : mode === "live" ? t("membership:wechat_pay", "微信支付") : t("membership:create_order", "创建订单")}
              </Button>
            )}
          </DialogActions>
        </Dialog>
      )}
    </Box>
  );
}
