import { useCallback, useEffect, useRef, useState } from "react";
import { membershipApi } from "../../../api/membershipApi";
import { notifyMembershipChanged } from "../../../features/membership/useMembership";
import type {
  BillingOrder,
  CreateBillingOrder,
} from "../../../features/membership/types";

interface PurchaseSelectionBase {
  sku: CreateBillingOrder["sku"];
  amountFen: number;
  catalogVersion: string;
}
export type PurchaseSelection = PurchaseSelectionBase & (
  | { kind: "membership"; planName: string; termDays: number; weekReportReference: number }
  | { kind: "topup"; credits: number }
);
interface CheckoutState {
  scope: string;
  selection: PurchaseSelection | null;
  order: BillingOrder | null;
  busy: boolean;
  cancelling?: boolean;
  error: "result_unknown" | "poll_error" | null;
}

/** Orders and their late responses belong to an account, auth state and environment. */
export function useMembershipCheckout(
  scope: string,
  authenticated: boolean,
  token: string | null,
) {
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const [state, setState] = useState<CheckoutState | null>(null);
  const active = useRef<AbortController | null>(null);
  const attempt = useRef<CreateBillingOrder | null>(null);
  const generation = useRef(0);
  const [pollRevision, setPollRevision] = useState(0);
  const settled = useRef(new Set<string>());
  const current = state?.scope === scope ? state : null;

  useEffect(() => {
    active.current?.abort();
    active.current = null;
    setState(null);
    attempt.current = null;
    generation.current += 1;
    settled.current.clear();
    return () => {
      active.current?.abort();
      active.current = null;
    };
  }, [scope]);

  const update = useCallback((order: BillingOrder, expectedScope: string) => {
    if (scopeRef.current !== expectedScope) return;
    setState((previous) =>
      previous?.scope === expectedScope
        ? { ...previous, order, busy: false, cancelling: false, error: null }
        : previous,
    );
    if (order.status === "paid" && !settled.current.has(order.id)) {
      settled.current.add(order.id);
      notifyMembershipChanged();
    }
  }, []);

  const select = (selection: PurchaseSelection) => {
    active.current?.abort();
    active.current = null;
    attempt.current = null;
    generation.current += 1;
    setState({ scope, selection, order: null, busy: false, error: null });
  };
  const openOrder = (order: BillingOrder) => {
    active.current?.abort();
    active.current = null;
    attempt.current = null;
    generation.current += 1;
    setState({ scope, selection: null, order, busy: false, error: null });
  };
  const close = () => {
    active.current?.abort();
    active.current = null;
    generation.current += 1;
    attempt.current = null;
    setState(null);
  };
  const create = async (provider: CreateBillingOrder["provider"]) => {
    if (!authenticated || !current?.selection || current.busy || active.current
      || current.order && (current.order.status !== "pending" || current.order.cancel_requested || Date.parse(current.order.expires_at) <= Date.now()))
      return;
    const controller = new AbortController();
    active.current = controller;
    const expectedScope = scope;
    const selection = current.selection;
    attempt.current ??= { sku: selection.sku, provider, idempotency_key: crypto.randomUUID() };
    setState({ ...current, busy: true, error: null });
    try {
      const order = await membershipApi.createOrder(
        attempt.current,
        token,
        controller.signal,
      );
      if (controller.signal.aborted || scopeRef.current !== expectedScope)
        return;
      update(order, expectedScope);
    } catch {
      if (!controller.signal.aborted && scopeRef.current === expectedScope) {
        setState((previous) =>
          previous?.scope === expectedScope
            ? {
                ...previous,
                busy: false,
                error: "result_unknown",
              }
            : previous,
        );
      }
    } finally {
      if (active.current === controller) active.current = null;
    }
  };

  const cancel = async () => {
    const order = current?.order;
    if (!authenticated || !order || order.provider !== "wechat" || order.status !== "pending" || current.busy || active.current) return;
    const controller = new AbortController();
    active.current = controller;
    generation.current += 1;
    setState(previous => previous?.scope === scope ? { ...previous, busy: true, cancelling: true, order: { ...order, cancel_requested: true, payment_url: null }, error: null } : previous);
    try {
      const next = await membershipApi.cancelOrder(order.id, token, controller.signal);
      if (!controller.signal.aborted && scopeRef.current === scope && next.id === order.id) update(next, scope);
    } catch {
      if (!controller.signal.aborted && scopeRef.current === scope) setState(previous => previous?.scope === scope ? { ...previous, busy: false, cancelling: false, error: "poll_error" } : previous);
    } finally {
      if (active.current === controller) active.current = null;
      if (!controller.signal.aborted && scopeRef.current === scope) setPollRevision(value => value + 1);
    }
  };
  const orderId = current?.order?.id;
  const pending = current?.order?.status === "pending";
  const cancelling = current?.cancelling;
  useEffect(() => {
    if (!authenticated || !orderId || !pending || cancelling) return;
    const controller = new AbortController();
    const expectedGeneration = generation.current;
    let timer: ReturnType<typeof setTimeout>;
    let inFlight = false;
    const isCurrent = () => !controller.signal.aborted && scopeRef.current === scope && generation.current === expectedGeneration;
    const poll = async () => {
      if (!isCurrent() || inFlight) return;
      if (document.visibilityState !== "visible") { timer = setTimeout(poll, 3000); return; }
      inFlight = true;
      try {
        const order = await membershipApi.getOrder(orderId, token, controller.signal);
        if (!isCurrent() || order.id !== orderId) return;
        update(order, scope);
        if (order.status !== "pending") return;
      } catch {
        if (!isCurrent()) return;
        setState(previous => previous?.scope === scope ? { ...previous, error: "poll_error" } : previous);
      } finally { inFlight = false; }
      if (isCurrent()) timer = setTimeout(poll, 3000);
    };
    const foreground = () => {
      if (document.visibilityState !== "visible" || inFlight) return;
      clearTimeout(timer); void poll();
    };
    timer = setTimeout(poll, 3000);
    document.addEventListener("visibilitychange", foreground);
    return () => { controller.abort(); clearTimeout(timer); document.removeEventListener("visibilitychange", foreground); };
  }, [authenticated, orderId, pending, cancelling, pollRevision, scope, token, update]);

  return { checkout: current, select, openOrder, close, create, cancel };
}
