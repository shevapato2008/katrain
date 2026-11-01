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
  formatSavings,
  planReportCopy,
  usagePercent,
} from "../../../features/membership/presentation";
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
const money = (fen: number) =>
  `¥${(fen / 100).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
const date = (at?: string | null) =>
  at && Number.isFinite(Date.parse(at))
    ? new Intl.DateTimeFormat("zh-CN", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(at))
    : "待确认";
const duration = (seconds: number | null) => {
  if (seconds === null) return "时间待确认";
  if (seconds === 0) return "正在确认最新额度";
  const days = Math.floor(seconds / 86400),
    hours = Math.floor((seconds % 86400) / 3600),
    minutes = Math.floor((seconds % 3600) / 60);
  return `${days ? `${days}天` : ""}${hours}小时${minutes}分钟`;
};
const depthCopy = (catalog: MembershipCatalog | null) => {
  if (!catalog || catalog.profiles.normal.credits_per_position <= 0)
    return "高级报告按服务端分析深度消耗。";
  const ratio =
    catalog.profiles.advanced.credits_per_position /
    catalog.profiles.normal.credits_per_position;
  return `高级报告消耗约 ${Number(ratio.toFixed(2))} 倍。`;
};
const orderStatus = (status: BillingOrder["status"]) =>
  ({
    pending: "等待付款",
    paid: "付款成功",
    expired: "订单已过期",
    failed: "付款失败",
    refunded: "已退款",
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
  const percent = usagePercent(period, true);
  const value = percent === "—" ? null : Number.parseFloat(percent);
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
          aria-valuetext={`剩余 ${percent}`}
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
          额度待确认
        </Typography>
      )}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        justifyContent="space-between"
        gap={0.5}
      >
        <Typography variant="body2" color="text.secondary">
          已用及分析中 {value === null ? "—" : `${(100 - value).toFixed(1)}%`}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {seconds === 0
            ? "正在确认最新额度"
            : seconds === null
              ? "时间待确认"
              : `${duration(seconds)}后${weekly ? "恢复" : "到期"}`}
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        {weekly
          ? "每周一 00:00（北京时间）恢复本周额度。"
          : `至 ${date(period?.reset_at)} 到期（北京时间）；周一恢复不增加本期额度。`}
      </Typography>
    </Box>
  );
}

function Rules({ catalog }: { catalog: MembershipCatalog | null }) {
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
        <Typography>会员与 API 计费规则</Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 0 }}>
        <Stack spacing={1.5} color="text.secondary">
          <Typography variant="body2">
            本期、本周分别按各自额度显示剩余比例，一次分析需同时满足两项剩余。分析中的预留计入已用，失败后归还。
            {depthCopy(catalog)}
          </Typography>
          <Typography variant="body2">
            优先使用会员额度；任一项会员剩余不足以完成本次分析时，整次使用已有
            API
            积分，不拆分扣费来源。积分不足时需充值或等待额度恢复，不自动购买积分或扣人民币。
          </Typography>
          <Typography variant="body2">
            开始分析前展示服务端报价与扣费来源。账户或用量状态未确认时暂不可开始分析。重复查看已拥有的结果、切换领地与支招，不重复收费。
          </Typography>
          <Typography variant="body2">
            按每盘 300 手、含初始局面估算，受本期剩余限制。
            {catalog?.plans
              .map(
                (plan) =>
                  `${plan.name} 每${plan.term_days}天本期普通报告参考约${plan.term_report_reference}盘`,
              )
              .join("；")}
            。每周一 00:00（北京时间）恢复本周额度；本期剩余到期结束。
          </Typography>
          <Typography variant="body2">
            续费在已有会员到期后顺延，不重置当前已用与预留；待付款日期仅为预计，最终生效区间以付款后的服务端回执为准。付费会员不叠加
            Free 普通报告资格。
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
                <Chip size="small" label="暂未开放" variant="outlined" />
              ) : plan.code === currentCode ? (
                <Chip
                  size="small"
                  label="当前会员"
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
                / {plan.term_days} 天
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
              比 API 约省 {formatSavings(plan.full_use_savings_percent)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              按 {plan.term_days} 天额度用满计算
            </Typography>
          </Box>
          <Box sx={{ p: 2.5, flex: 1 }}>
            <Typography sx={{ fontSize: 17 }}>
              {planReportCopy(plan.week_report_reference)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              按每盘 300 手估算，受本期剩余限制。{depthCopy(catalog)}
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
                  ? `${plan.name} 暂未开放`
                  : `${plan.code === currentCode ? "续费" : "选择"} ${plan.name}`
              }
            >
              {!plan.sale_enabled
                ? "暂未开放"
                : `${plan.code === currentCode ? "续费" : "选择"} ${plan.name}`}
            </Button>
          </Box>
        </Paper>
      ))}
    </Box>
  );
}

export default function MembershipPage() {
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
  const { checkout, select, openOrder, close, create } = useMembershipCheckout(
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
  // This release only supports isolated TEST orders; real merchant checkout is not configured.
  const safePaymentMode =
    mode === "mock" && catalog?.environment.toLowerCase() === "test";
  const canPay =
    ordersEnabled && safePaymentMode && usage.payments_mode === mode;
  const canBuyMembership =
    !!canPay &&
    !!catalog?.capabilities.membership &&
    !!usage?.capabilities.membership;
  const paymentNotice = !ready
    ? "账户与用量确认后，才能创建付款订单。"
    : !canPay
      ? "支付暂未开放，当前不能创建付款订单。"
      : null;
  const topup =
    catalog?.topups.find((item) => item.sku === selectedSku) ??
    catalog?.topups.find((item) => item.sku === "topup_30") ??
    catalog?.topups[0];
  const choosePlan = (plan: MembershipPlan) => {
    if (!catalog || !canBuyMembership || !plan.sale_enabled) return;
    select({
      sku: `membership_${plan.code}`,
      name: `${plan.name} · ${plan.term_days} 天会员`,
      kind: "membership",
      amountFen: plan.amount_fen,
      catalogVersion: catalog.catalog_version,
      detail: planReportCopy(plan.week_report_reference),
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
      name: "API 积分充值",
      kind: "topup",
      amountFen: topup.amount_fen,
      catalogVersion: catalog.catalog_version,
      detail: `到账 ${formatPoints(topup.credits)} 积分`,
    });
  };
  const loadHistory = async () => {
    if (
      !authenticated ||
      !catalog?.capabilities.orders ||
      !usage?.capabilities.orders
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
      ? "已同步"
      : stale
        ? "待更新"
        : status === "loading"
          ? "正在确认"
          : status === "unavailable"
            ? "暂不可用"
            : "待确认";
  const currentPlan = verifiedUsage ? usage.plan.current : null;
  const wallet = verifiedUsage ? formatPoints(usage.wallet?.credits) : "—";
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
            ? "正在确认账户"
            : auth.status === "unavailable"
              ? "账户状态暂未确认"
              : "登录后查看会员与用量"}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          确认账户身份后，显示会员权益、Free 资格与 API 积分余额。
        </Typography>
        {auth.status === "checking" ? (
          <CircularProgress size={24} aria-label="正在确认账户" />
        ) : auth.status === "unavailable" ? (
          <Button variant="outlined" onClick={() => void auth.retry()}>
            重试账户验证
          </Button>
        ) : (
          <Button variant="contained" onClick={() => setLoginOpen(true)}>
            登录账户
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
            <Typography>正在读取会员与用量…</Typography>
          </Stack>
        ) : (
          <>
            <Typography variant="h6" sx={{ mb: 1 }}>
              会员与用量暂不可用
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              账户权益与余额尚未确认，请稍后重试。
            </Typography>
            <Button variant="outlined" onClick={() => void refresh()}>
              重新载入
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
                  会员额度
                </Typography>
                <Chip
                  label={stale ? "扣费来源待确认" : "优先使用会员额度"}
                  variant="outlined"
                  size="small"
                />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                会员不足以完成本次分析时，整次使用已有 API 积分。
              </Typography>
              <Quota
                label="本期剩余"
                period={verifiedUsage ? usage.term : null}
                seconds={countdowns.term}
              />
              <Quota
                label="本周剩余"
                period={verifiedUsage ? usage.week : null}
                seconds={countdowns.week}
                weekly
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                两项剩余分别计算，一次分析需同时满足。分析中的预留已计入使用比例，失败后归还。
              </Typography>
            </>
          ) : !verifiedUsage ? (
            <>
              <Typography component="h2" variant="h5" sx={{ mb: 2 }}>
                账户权益待确认
              </Typography>
              <Typography color="text.secondary">
                会员与 Free 资格尚未确认，请重新载入后查看。
              </Typography>
            </>
          ) : (
            <>
              <Typography component="h2" variant="h5" sx={{ mb: 2 }}>
                Free · 本周普通报告资格
              </Typography>
              {verifiedUsage &&
              usage.capabilities.can_claim_free_report &&
              usage.free?.eligible ? (
                <>
                  <Typography variant="h4" sx={{ mb: 2 }}>
                    本周剩余 {usage.free.remaining} 份
                  </Typography>
                  <Typography color="text.secondary">
                    每自然周 {usage.free.limit}{" "}
                    份普通报告的独立领取资格；需满足身份验证条件，不作为通用分析额度。
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 2 }}
                  >
                    {duration(countdowns.free)}后恢复 ·{" "}
                    {date(usage.free.reset_at)}（北京时间）
                  </Typography>
                </>
              ) : (
                <>
                  <Typography variant="h6" sx={{ mb: 1 }}>
                    {verifiedUsage && usage.free && !usage.free.eligible
                      ? "Free 资格当前不可用"
                      : "Free 资格待确认"}
                  </Typography>
                  <Typography color="text.secondary">
                    Free
                    普通报告需先满足可信身份条件。当前不提供可领取数量，付费会员不叠加
                    Free 报告资格。
                  </Typography>
                </>
              )}
              <Button sx={{ mt: 2 }} onClick={() => setTab("plans")}>
                比较会员与 API
              </Button>
            </>
          )}
        </Paper>
        <Stack gap={2.5}>
          <Paper variant="outlined" sx={cardSx}>
            <Typography color="text.secondary" variant="body2">
              当前会员
            </Typography>
            <Typography variant="h4" sx={{ mt: 1, mb: 1.5 }}>
              {verifiedUsage ? (currentPlan?.name ?? "Free") : "待确认"}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {currentPlan
                ? `有效期至 ${date(currentPlan.ends_at)}（北京时间）`
                : verifiedUsage
                  ? "每自然周的独立普通报告资格"
                  : "会员权益待确认"}
            </Typography>
            {verifiedUsage && usage.plan.next && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                已购 {usage.plan.next.name} · {date(usage.plan.next.starts_at)}{" "}
                生效
              </Typography>
            )}
            <Button
              fullWidth
              variant="outlined"
              sx={{ mt: 2 }}
              onClick={() => setTab("plans")}
            >
              查看会员方案
            </Button>
          </Paper>
          <Paper variant="outlined" sx={cardSx}>
            <Typography color="text.secondary" variant="body2">
              API 积分余额
            </Typography>
            <Typography variant="h4" sx={{ my: 1, ...numberSx }}>
              {wallet}
              <Typography
                component="span"
                color="text.secondary"
                sx={{ fontSize: 15, ml: 1 }}
              >
                积分
              </Typography>
            </Typography>
            <Typography color="text.secondary" variant="body2">
              1 元 = 1 积分
            </Typography>
            <Typography variant="body2" color="text.secondary">
              普通约 {normal ? formatPoints(normal.credits_per_position) : "—"}{" "}
              积分/手
              <br />
              高级约{" "}
              {advanced
                ? formatPoints(advanced.credits_per_position)
                : "—"}{" "}
              积分/手
            </Typography>
            <Button
              fullWidth
              variant="outlined"
              sx={{ mt: 2 }}
              onClick={() => setTab("recharge")}
            >
              API 充值
            </Button>
          </Paper>
        </Stack>
      </Box>
    );
  } else if (tab === "plans") {
    body = (
      <>
        <Typography component="h2" variant="h5" sx={{ mb: 1 }}>
          按你的用量，选择会员
        </Typography>
        <Typography color="text.secondary" variant="body2" sx={{ mb: 2.5 }}>
          按本期额度用满计算优惠；实际优惠随用量变化。续费在已有会员到期后顺延。
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
            <Typography variant="h6">偶尔分析，也可以按需充值</Typography>
            <Typography variant="body2" color="text.secondary">
              API 无需订阅，1 元 = 1 积分。分析开始前确认服务端报价。
            </Typography>
          </Box>
          <Button variant="outlined" onClick={() => setTab("recharge")}>
            查看 API 充值
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
              API 按需分析
            </Typography>
            <Table
              size="small"
              aria-label="API 分析价格"
              sx={{
                mt: 1,
                "& th, & td": { px: 0, py: 1.5 },
                "& td": { fontSize: 16 },
              }}
            >
              <TableHead>
                <TableRow>
                  <TableCell>分析深度</TableCell>
                  <TableCell align="right">每手费用</TableCell>
                  <TableCell align="right">计算量</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(["normal", "advanced"] as const).map((key) => (
                  <TableRow key={key}>
                    <TableCell>{key === "normal" ? "普通" : "高级"}</TableCell>
                    <TableCell align="right">
                      <Typography
                        component="span"
                        sx={{ fontSize: 24, ...numberSx }}
                      >
                        {formatPoints(
                          catalog.profiles[key].credits_per_position,
                        )}
                      </Typography>{" "}
                      <Typography
                        component="span"
                        variant="body2"
                        color="text.secondary"
                      >
                        积分
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {catalog.profiles[key].visits} visits
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              单局面与整盘使用相同单价；整盘按手数加初始局面计费。
            </Typography>
          </Box>
          <Box
            sx={{ p: { xs: 2, sm: 3 }, bgcolor: "#eae2cd", color: "#223729" }}
          >
            <Typography variant="body2">一盘 300 手，花费多少？</Typography>
            <ToggleButtonGroup
              value={profile}
              exclusive
              size="small"
              onChange={(_, value: MembershipProfile | null) =>
                value && setProfile(value)
              }
              aria-label="示例分析深度"
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
              <ToggleButton value="normal">普通</ToggleButton>
              <ToggleButton value="advanced">高级</ToggleButton>
            </ToggleButtonGroup>
            <Typography variant="h3" sx={{ fontSize: 36, mb: 1, color: "inherit", ...numberSx }}>
              {rate ? formatPoints(rate.credits_per_position * 301) : "—"}
              <Typography component="span" sx={{ fontSize: 16, ml: 1 }}>
                积分
              </Typography>
            </Typography>
            <Typography variant="body2">
              含初始局面，共 301 个分析局面。实际费用以提交前服务端报价为准。
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
                  API 积分余额
                </Typography>
                <Typography variant="h4" sx={{ mt: 0.5, ...numberSx }}>
                  {wallet}
                  <Typography component="span" sx={{ fontSize: 15, ml: 1 }}>
                    积分
                  </Typography>
                </Typography>
              </Box>
              <Typography color="text.secondary" variant="body2">
                1 元 = 1 积分
                <br />
                按需购买，无需订阅
              </Typography>
            </Stack>
            <Divider sx={{ my: 2.5 }} />
            <Typography component="h2" variant="h6">
              选择充值金额
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
                  aria-label={`${item.amount_fen / 100} 元，到账 ${formatPoints(item.credits)} 积分`}
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
                    sx={{ fontSize: 25, ...numberSx }}
                  >
                    {item.amount_fen / 100}
                    <Typography component="span" sx={{ fontSize: 14, ml: 0.5 }}>
                      元
                    </Typography>
                  </Typography>
                  <Typography
                    component="span"
                    sx={{ fontSize: { xs: 12, sm: 14 }, whiteSpace: "nowrap" }}
                  >
                    {formatPoints(item.credits)} 积分
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
              充值 {topup ? topup.amount_fen / 100 : "—"} 元
            </Button>
            <Typography color="text.secondary" variant="body2" sx={{ mt: 1.5 }}>
              付款确认后到账。会员不足时使用已有 API 积分，不自动充值。
            </Typography>
          </Paper>
          <Paper variant="outlined" sx={cardSx}>
            <Typography component="h2" variant="h5">
              常用分析，会员更省
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              同等普通分析量，按本期额度用满计算。
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
                      {plan.name} · {money(plan.amount_fen)} / {plan.term_days}{" "}
                      天
                    </Typography>
                    <Typography color="text.secondary" variant="body2">
                      每周最多约 {plan.week_report_reference} 盘
                      {!plan.sale_enabled ? " · 暂未开放" : ""}
                    </Typography>
                  </Box>
                  <Typography sx={{ whiteSpace: "nowrap" }}>
                    约省 {formatSavings(plan.full_use_savings_percent)}
                  </Typography>
                </Stack>
              ))}
            </Stack>
            <Typography color="text.secondary" variant="body2" sx={{ mt: 1 }}>
              按每盘 300 手估算，受本期剩余限制。{depthCopy(catalog)}
            </Typography>
            <Button sx={{ mt: 1 }} onClick={() => setTab("plans")}>
              比较会员方案
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
        title="会员与用量"
        status={<Chip size="small" variant="outlined" label={titleStatus} />}
      />
      <Stack
        direction="row"
        gap={1}
        alignItems="center"
        justifyContent="space-between"
        sx={{ mt: 1, mb: 2 }}
      >
        <Typography color="text.secondary" variant="body2">
          查看分析用量，选择按需充值或会员。
        </Typography>
        {authenticated && (
          <Button
            size="small"
            startIcon={<RefreshIcon />}
            onClick={() => void refresh()}
            sx={{ whiteSpace: "nowrap", minHeight: 44 }}
          >
            刷新
          </Button>
        )}
      </Stack>
      <Tabs
        value={tab}
        onChange={(_, next: string) => setTab(next)}
        aria-label="会员页面"
        sx={{
          mb: 3,
          borderBottom: "1px solid",
          borderColor: "divider",
          "& .MuiTab-root": { fontSize: 18, minHeight: 48 },
          "& .MuiTab-root.Mui-selected": { color: "#b7d9c2" },
          "& .MuiTabs-indicator": { bgcolor: "#b7d9c2" },
        }}
      >
        <Tab value="usage" label="用量" />
        <Tab value="recharge" label="API 充值" />
        <Tab value="plans" label="会员" />
      </Tabs>
      {stale && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          当前显示上次载入的数据；账户与扣费来源待重新确认，购买暂不可用。
        </Alert>
      )}
      {status === "unavailable" && (
        <Alert severity="info" sx={{ mb: 2 }}>
          当前服务未开放会员用量，权益与余额待确认。
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
              余额与权益以服务端确认结果为准。
            </Typography>
            <Button
              onClick={() => void loadHistory()}
              disabled={
                !catalog.capabilities.orders || !usage.capabilities.orders
              }
            >
              订单记录
            </Button>
          </Stack>
          {currentHistory && (
            <Paper variant="outlined" sx={{ ...cardSx, mt: 2 }}>
              <Typography variant="h6" sx={{ mb: 1.5 }}>
                订单记录
              </Typography>
              {currentHistory.status === "loading" ? (
                <CircularProgress size={24} />
              ) : currentHistory.status === "error" ? (
                <Alert
                  severity="warning"
                  action={
                    <Button onClick={() => void loadHistory()}>重试</Button>
                  }
                >
                  订单记录暂不可用
                </Alert>
              ) : !currentHistory.orders.length ? (
                <Typography color="text.secondary">暂无订单</Typography>
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
                          {item.kind === "topup" ? "API 积分充值" : "会员订单"}{" "}
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
                        {orderStatus(item.status)}
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
            {order ? orderStatus(order.status) : "确认购买"}
          </DialogTitle>
          <DialogContent>
            {(order?.payments_mode === "mock" ||
              (!order && mode === "mock")) && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                TEST 模拟订单，不会真实收款
              </Alert>
            )}
            <Typography variant="h6">
              {selection?.name ??
                (order?.kind === "topup" ? "API 积分充值" : "会员订单")}
            </Typography>
            <Typography
              variant="h3"
              sx={{ fontSize: 36, mt: 1.5, mb: 2, ...numberSx }}
            >
              {money(order?.amount_fen ?? selection?.amountFen ?? 0)}
            </Typography>
            {selection && (
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                {selection.detail}
              </Typography>
            )}
            {!order && selection?.kind === "membership" && (
              <Typography variant="body2" color="text.secondary">
                在已有会员到期后顺延，不重置当前额度。生效日期以付款后的服务端回执为准。
              </Typography>
            )}
            {order && (
              <>
                <Typography variant="body2" color="text.secondary">
                  订单编号
                </Typography>
                <Typography sx={{ overflowWrap: "anywhere", mb: 2 }}>
                  {order.id}
                </Typography>
                <Alert
                  severity={
                    order.status === "paid"
                      ? "success"
                      : ["failed", "expired"].includes(order.status)
                        ? "warning"
                        : "info"
                  }
                >
                  {orderStatus(order.status)}
                  {order.status === "pending"
                    ? "，页面将自动确认服务端状态。"
                    : ""}
                </Alert>
                {order.status === "pending" && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 1.5 }}
                  >
                    订单有效期至 {date(order.expires_at)}（北京时间）。
                    {order.estimated_starts_at && (
                      <>
                        预计生效 {date(order.estimated_starts_at)}，预计到期{" "}
                        {date(order.estimated_ends_at)}
                        ；最终日期以付款回执为准。
                      </>
                    )}
                  </Typography>
                )}
                {order.status === "paid" && order.fulfillment && (
                  <Box sx={{ mt: 2 }}>
                    {order.kind === "topup" ? (
                      <Typography>
                        实际到账 {formatPoints(order.fulfillment.credits)} 积分
                      </Typography>
                    ) : (
                      <Typography>
                        实际生效 {date(order.fulfillment.starts_at)}
                        <br />
                        实际到期 {date(order.fulfillment.ends_at)}（北京时间）
                      </Typography>
                    )}
                  </Box>
                )}
                {order.status === "paid" && !order.fulfillment && (
                  <Typography color="text.secondary" sx={{ mt: 2 }}>
                    权益回执待确认，请刷新用量查看。
                  </Typography>
                )}
                {order.status === "pending" && order.provider === "live" && (
                  <Typography color="text.secondary" sx={{ mt: 2 }}>
                    支付渠道接入尚未开放，请勿在页面外向未知账户付款。
                  </Typography>
                )}
              </>
            )}
            {checkout?.error && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                {checkout.error}
              </Alert>
            )}
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={close}>
              {order?.status === "paid" ? "完成" : "关闭"}
            </Button>
            {!order && (
              <Button
                variant="contained"
                disabled={
                  !canPay ||
                  !confirmedSelection ||
                  checkout?.busy ||
                  !!checkout?.error
                }
                onClick={() => {
                  if (
                    canPay &&
                    confirmedSelection &&
                    (mode === "mock" || mode === "live")
                  )
                    void create(mode);
                }}
              >
                {checkout?.busy ? "正在创建…" : "创建订单"}
              </Button>
            )}
          </DialogActions>
        </Dialog>
      )}
    </Box>
  );
}
