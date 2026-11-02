import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MembershipPage from "./MembershipPage";
import type {
  BillingOrder,
  MembershipCatalog,
  MembershipUsage,
} from "../../../features/membership/types";

const mocks = vi.hoisted(() => ({
  auth: {
    identityKey: "account-a",
    status: "authenticated",
    token: null as string | null,
    user: { username: "fan" },
    retry: vi.fn(),
  },
  membership: {} as Record<string, unknown>,
  createOrder: vi.fn(),
  getOrder: vi.fn(),
  getOrders: vi.fn(),
  changed: vi.fn(),
}));
vi.mock("../../../context/AuthContext", () => ({ useAuth: () => mocks.auth }));
vi.mock("../../../features/membership/useMembership", () => ({
  useMembership: () => mocks.membership,
  notifyMembershipChanged: mocks.changed,
}));
vi.mock("../../../api/membershipApi", () => ({
  membershipApi: {
    createOrder: mocks.createOrder,
    getOrder: mocks.getOrder,
    getOrders: mocks.getOrders,
  },
}));
vi.mock("../../components/layout/ContentPageHeader", () => ({
  default: ({ title }: { title: string }) => <h1>{title}</h1>,
}));
vi.mock("../../components/auth/LoginModal", () => ({
  default: ({ open }: { open: boolean }) =>
    open ? <div role="dialog">登录账户</div> : null,
}));

const capabilities = {
  membership: true,
  usage: true,
  quotes: true,
  positions: true,
  orders: true,
  can_claim_free_report: true,
};
const makeCatalog = (): MembershipCatalog => ({
  catalog_version: "v1",
  server_now: "2026-11-02T04:00:00Z",
  environment: "test",
  membership_mode: "enabled",
  capabilities: { ...capabilities },
  payments_mode: "mock",
  plans: [
    {
      code: "plus",
      name: "Plus",
      amount_fen: 3900,
      term_days: 30,
      term_units: 9030,
      week_units: 3010,
      term_report_reference: 30,
      week_report_reference: 10,
      full_use_savings_percent: 56.8,
      sale_enabled: true,
    },
    {
      code: "pro",
      name: "Pro",
      amount_fen: 9900,
      term_days: 30,
      term_units: 27090,
      week_units: 9030,
      term_report_reference: 90,
      week_report_reference: 30,
      full_use_savings_percent: 63.5,
      sale_enabled: true,
    },
    {
      code: "max",
      name: "Max",
      amount_fen: 19900,
      term_days: 30,
      term_units: 72240,
      week_units: 24080,
      term_report_reference: 240,
      week_report_reference: 80,
      full_use_savings_percent: 72.5,
      sale_enabled: false,
    },
  ],
  topups: [
    {
      sku: "topup_10",
      amount_fen: 1000,
      credits: 1000,
      display_points: "10.00",
    },
    {
      sku: "topup_30",
      amount_fen: 3000,
      credits: 3000,
      display_points: "30.00",
    },
    {
      sku: "topup_100",
      amount_fen: 10000,
      credits: 10000,
      display_points: "100.00",
    },
  ],
  profiles: {
    normal: {
      visits: 500,
      credits_per_position: 1,
      display_points_per_position: "0.01",
    },
    advanced: {
      visits: 2000,
      credits_per_position: 4,
      display_points_per_position: "0.04",
    },
  },
});
const makeUsage = (): MembershipUsage => ({
  catalog_version: "v1",
  server_now: "2026-11-02T04:00:00Z",
  revision: 1,
  environment: "test",
  capabilities: { ...capabilities },
  payments_mode: "mock",
  plan: {
    current: {
      code: "pro",
      name: "Pro",
      starts_at: "2026-11-01T04:00:00Z",
      ends_at: "2026-12-01T04:00:00Z",
    },
    next: null,
  },
  term: {
    limit: 27090,
    used: 10000,
    reserved: 400,
    remaining: 16690,
    percent: 61.6,
    reset_at: "2026-12-01T04:00:00Z",
  },
  week: {
    limit: 9030,
    used: 7000,
    reserved: 224,
    remaining: 1806,
    percent: 20,
    reset_at: "2026-11-09T00:00:00+08:00",
  },
  wallet: { credits: 1234, display_points: "12.34" },
  free: null,
});
const pendingOrder = (): BillingOrder => ({
  id: "order-a",
  sku: "membership_plus",
  kind: "membership",
  status: "pending",
  amount_fen: 3900,
  currency: "CNY",
  payments_mode: "mock",
  provider: "mock",
  created_at: "2026-11-02T04:00:00Z",
  expires_at: "2026-11-02T04:15:00Z",
  paid_at: null,
  fulfillment: null,
  estimated_starts_at: "2026-12-01T04:00:00Z",
  estimated_ends_at: "2026-12-31T04:00:00Z",
});
const show = (tab = "usage") =>
  render(
    <MemoryRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      initialEntries={[`/galaxy/membership?tab=${tab}`]}
    >
      <MembershipPage />
    </MemoryRouter>,
  );
const startOrder = async () => {
  fireEvent.click(screen.getByRole("button", { name: "选择 Plus" }));
  fireEvent.click(screen.getByRole("button", { name: "创建订单" }));
  await screen.findByText("order-a");
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.auth.identityKey = "account-a";
  mocks.auth.status = "authenticated";
  mocks.auth.token = null;
  mocks.membership = {
    catalog: makeCatalog(),
    usage: makeUsage(),
    status: "ready",
    error: null,
    refresh: vi.fn(),
    countdowns: { term: 2505600, week: 561600, free: null },
  };
  mocks.createOrder.mockResolvedValue(pendingOrder());
  mocks.getOrder.mockResolvedValue(pendingOrder());
  mocks.getOrders.mockResolvedValue({ orders: [] });
});

describe("Galaxy membership", () => {
  it("shows each period percentage, server countdowns and integer-credit wallet without internal units", () => {
    show();
    expect(
      screen.getByRole("progressbar", { name: "本期剩余" }),
    ).toHaveAttribute("aria-valuenow", "61.6");
    expect(
      screen.getByRole("progressbar", { name: "本周剩余" }),
    ).toHaveAttribute("aria-valuenow", "20");
    expect(screen.getByText("12.34")).toBeInTheDocument();
    expect(screen.getByText(/6天12小时/)).toBeInTheDocument();
    expect(
      screen.queryByText(/标准单位|27090|9030|每日次数/),
    ).not.toBeInTheDocument();
  });

  it("uses catalog prices, references and savings and keeps Max unavailable", () => {
    const catalog = makeCatalog();
    catalog.plans[0].amount_fen = 4200;
    catalog.plans[0].week_report_reference = 12;
    catalog.plans[0].term_days = 28;
    catalog.plans[0].term_report_reference = 37;
    mocks.membership.catalog = catalog;
    show("plans");
    expect(screen.getByText("¥42")).toBeInTheDocument();
    expect(screen.getByText("普通报告，每周最多约12盘")).toBeInTheDocument();
    expect(screen.getByText("28天共约37盘")).toBeInTheDocument();
    expect(screen.getByText(/56.8%/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Max 暂未开放" })).toBeDisabled();
    expect(
      screen.getAllByText(/按每盘 300 手估算，受本期剩余限制/).length,
    ).toBeGreaterThan(0);
  });

  it("allows a sale-enabled Max selection with the catalog's 199 yuan preview", () => {
    const catalog = makeCatalog();
    catalog.plans[2].sale_enabled = true;
    mocks.membership.catalog = catalog;
    show("plans");
    fireEvent.click(screen.getByRole("button", { name: "选择 Max" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("¥199");
    expect(screen.getByRole("button", { name: "创建订单" })).toBeEnabled();
    expect(mocks.createOrder).not.toHaveBeenCalled();
  });

  it("shows API prices and topups from catalog, with 301-position report example", () => {
    const catalog = makeCatalog();
    catalog.profiles.normal.credits_per_position = 2;
    catalog.profiles.normal.display_points_per_position = "0.02";
    mocks.membership.catalog = catalog;
    show("recharge");
    expect(screen.getByText("0.02")).toBeInTheDocument();
    expect(screen.getByText(/6.02/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /30 元.*30.00 积分/ }),
    ).toBeInTheDocument();
  });

  it("does not turn an unknown Free entitlement into zero eligibility", () => {
    const usage = makeUsage();
    usage.plan.current = null;
    usage.term = null;
    usage.week = null;
    usage.capabilities.can_claim_free_report = false;
    mocks.membership.usage = usage;
    show();
    expect(screen.getByText("Free 资格待确认")).toBeInTheDocument();
    expect(screen.queryByText("本周剩余 0 份")).not.toBeInTheDocument();
  });

  it("retains an explicitly stale snapshot while blocking new payment", () => {
    mocks.membership.status = "error";
    mocks.membership.error = new Error("offline");
    show("plans");
    expect(screen.getByText(/上次载入的数据/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择 Plus" })).toBeDisabled();
  });

  it("shows login for a guest and preserves cookie-authenticated accounts without a token", async () => {
    mocks.auth.status = "guest";
    mocks.auth.identityKey = "";
    mocks.membership = {
      ...mocks.membership,
      status: "unauthenticated",
      catalog: null,
      usage: null,
    };
    show();
    fireEvent.click(screen.getByRole("button", { name: "登录账户" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("登录账户");
  });

  it("does not create an order when payments or order capability are disabled", () => {
    const catalog = makeCatalog();
    catalog.plans[2].sale_enabled = true;
    catalog.payments_mode = "disabled";
    mocks.membership.catalog = catalog;
    show("plans");
    expect(screen.getByText(/支付暂未开放/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择 Plus" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "选择 Max" })).toBeDisabled();
    expect(mocks.createOrder).not.toHaveBeenCalled();
  });

  it("creates an order with only sku, provider and idempotency and marks mock payments honestly", async () => {
    show("plans");
    await startOrder();
    expect(mocks.createOrder).toHaveBeenCalledWith(
      {
        sku: "membership_plus",
        provider: "mock",
        idempotency_key: expect.any(String),
      },
      null,
      expect.any(AbortSignal),
    );
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "TEST 模拟订单，不会真实收款",
    );
    expect(screen.getByRole("dialog")).toHaveTextContent("预计生效");
    expect(
      screen.queryByRole("button", { name: "我已付款" }),
    ).not.toBeInTheDocument();
    expect(mocks.changed).not.toHaveBeenCalled();
  });

  it("refreshes only after server-confirmed paid and displays fulfilled dates", async () => {
    const paid = {
      ...pendingOrder(),
      status: "paid" as const,
      paid_at: "2026-11-02T04:01:00Z",
      fulfillment: {
        starts_at: "2026-12-02T04:00:00Z",
        ends_at: "2027-01-01T04:00:00Z",
        plan_code: "plus" as const,
      },
    };
    mocks.createOrder.mockResolvedValue(paid);
    show("plans");
    await startOrder();
    await waitFor(() => expect(mocks.changed).toHaveBeenCalledOnce());
    expect(screen.getByRole("dialog")).toHaveTextContent("实际生效");
    expect(screen.getByRole("dialog")).toHaveTextContent("2026/12/02");
  });

  it("hides a previous identity order immediately and discards its late response", async () => {
    let resolve!: (order: BillingOrder) => void;
    mocks.createOrder.mockImplementation(
      () =>
        new Promise<BillingOrder>((done) => {
          resolve = done;
        }),
    );
    const view = show("plans");
    fireEvent.click(screen.getByRole("button", { name: "选择 Plus" }));
    fireEvent.click(screen.getByRole("button", { name: "创建订单" }));
    const signal = mocks.createOrder.mock.calls[0][2] as AbortSignal;
    mocks.auth.identityKey = "account-b";
    view.rerender(
      <MemoryRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        initialEntries={["/galaxy/membership?tab=plans"]}
      >
        <MembershipPage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(signal.aborted).toBe(true);
    await act(async () => resolve({ ...pendingOrder(), status: "paid" }));
    expect(screen.queryByText("order-a")).not.toBeInTheDocument();
    expect(mocks.changed).not.toHaveBeenCalled();
  });
  it.each(["production-mock", "production-live", "orders-disabled"])(
    "blocks unsupported payment boundary %s",
    (boundary) => {
      const catalog = makeCatalog(),
        usage = makeUsage();
      if (boundary.startsWith("production"))
        catalog.environment = usage.environment = "production";
      if (boundary === "production-live")
        catalog.payments_mode = usage.payments_mode = "live";
      if (boundary === "orders-disabled") usage.capabilities.orders = false;
      mocks.membership = { ...mocks.membership, catalog, usage };
      show("plans");
      expect(screen.getByRole("button", { name: "选择 Plus" })).toBeDisabled();
      expect(mocks.createOrder).not.toHaveBeenCalled();
    },
  );

  it("does not classify unavailable entitlements as Free membership", () => {
    mocks.membership.status = "unavailable";
    show();
    expect(screen.getByText("账户权益待确认")).toBeInTheDocument();
    expect(
      screen.queryByText("Free · 本周普通报告资格"),
    ).not.toBeInTheDocument();
  });

  it("aborts previous-account order polling and drops its late paid response", async () => {
    let resolve!: (order: BillingOrder) => void;
    mocks.getOrder.mockImplementation(
      () =>
        new Promise<BillingOrder>((done) => {
          resolve = done;
        }),
    );
    const view = show("plans");
    await startOrder();
    await waitFor(() => expect(mocks.getOrder).toHaveBeenCalledOnce(), {
      timeout: 4000,
    });
    const signal = mocks.getOrder.mock.calls[0][2] as AbortSignal;
    expect(mocks.getOrder).toHaveBeenCalledWith("order-a", null, signal);
    mocks.auth.identityKey = "account-b";
    view.rerender(
      <MemoryRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        initialEntries={["/galaxy/membership?tab=plans"]}
      >
        <MembershipPage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(signal.aborted).toBe(true);
    await act(async () =>
      resolve({
        ...pendingOrder(),
        status: "paid",
        fulfillment: { plan_code: "plus" },
      }),
    );
    expect(screen.queryByText("order-a")).not.toBeInTheDocument();
    expect(mocks.changed).not.toHaveBeenCalled();
  });
});
