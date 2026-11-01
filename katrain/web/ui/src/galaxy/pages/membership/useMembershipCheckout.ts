import { useCallback, useEffect, useRef, useState } from "react";
import { membershipApi } from "../../../api/membershipApi";
import { notifyMembershipChanged } from "../../../features/membership/useMembership";
import type {
  BillingOrder,
  CreateBillingOrder,
} from "../../../features/membership/types";

export interface PurchaseSelection {
  sku: CreateBillingOrder["sku"];
  kind: "membership" | "topup";
  name: string;
  amountFen: number;
  catalogVersion: string;
  detail: string;
}
interface CheckoutState {
  scope: string;
  selection: PurchaseSelection | null;
  order: BillingOrder | null;
  busy: boolean;
  error: string | null;
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
  const settled = useRef(new Set<string>());
  const current = state?.scope === scope ? state : null;

  useEffect(() => {
    active.current?.abort();
    active.current = null;
    setState(null);
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
        ? { ...previous, order, busy: false, error: null }
        : previous,
    );
    if (order.status === "paid" && !settled.current.has(order.id)) {
      settled.current.add(order.id);
      notifyMembershipChanged();
    }
  }, []);

  const select = (selection: PurchaseSelection) => {
    active.current?.abort();
    setState({ scope, selection, order: null, busy: false, error: null });
  };
  const openOrder = (order: BillingOrder) => {
    active.current?.abort();
    setState({ scope, selection: null, order, busy: false, error: null });
  };
  const close = () => {
    active.current?.abort();
    active.current = null;
    setState(null);
  };
  const create = async (provider: "mock" | "live") => {
    if (!authenticated || !current?.selection || current.busy || active.current)
      return;
    const controller = new AbortController();
    active.current = controller;
    const expectedScope = scope;
    const selection = current.selection;
    setState({ ...current, busy: true, error: null });
    try {
      const order = await membershipApi.createOrder(
        { sku: selection.sku, provider, idempotency_key: crypto.randomUUID() },
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
                error: "订单结果暂未确认，请先查看订单记录，避免重复创建。",
              }
            : previous,
        );
      }
    } finally {
      if (active.current === controller) active.current = null;
    }
  };

  const orderId = current?.order?.id;
  const pending = current?.order?.status === "pending";
  useEffect(() => {
    if (!authenticated || !orderId || !pending) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (document.visibilityState !== "visible") {
        timer = setTimeout(poll, 3000);
        return;
      }
      try {
        const order = await membershipApi.getOrder(
          orderId,
          token,
          controller.signal,
        );
        if (
          controller.signal.aborted ||
          scopeRef.current !== scope ||
          order.id !== orderId
        )
          return;
        update(order, scope);
        if (order.status !== "pending") return;
      } catch {
        if (controller.signal.aborted || scopeRef.current !== scope) return;
        setState((previous) =>
          previous?.scope === scope
            ? {
                ...previous,
                error: "暂时无法确认付款状态，正在重试。请勿重复付款。",
              }
            : previous,
        );
      }
      timer = setTimeout(poll, 3000);
    };
    // The create response is already an authoritative status; follow-up polling is bounded.
    timer = setTimeout(poll, 3000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [authenticated, orderId, pending, scope, token, update]);

  return { checkout: current, select, openOrder, close, create };
}
