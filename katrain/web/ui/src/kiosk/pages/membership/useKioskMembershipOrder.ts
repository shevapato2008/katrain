import { useCallback, useEffect, useRef, useState } from 'react';
import { membershipApi } from '../../../api/membershipApi';
import { useAuth } from '../../../context/AuthContext';
import type { BillingOrder, CreateBillingOrder } from '../../../features/membership/types';
import { notifyMembershipChanged } from '../../../features/membership/useMembership';

/** Orders stay scoped to the authenticated identity, including cookie-only box sessions. */
export function useKioskMembershipOrder(environment?: string) {
  const { identityKey, status, token } = useAuth();
  const scope = JSON.stringify([identityKey, status, environment]);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const authenticated = status === 'authenticated' && identityKey !== null;
  const [state, setState] = useState<{ scope: string; order: BillingOrder | null; creating: boolean; error: string | null } | null>(null);
  const [history, setHistory] = useState<{ scope: string; orders: BillingOrder[]; loading: boolean; error: string | null } | null>(null);
  const request = useRef<AbortController | null>(null);
  const historyRequest = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const paidOrders = useRef(new Set<string>());
  const current = state?.scope === scope && authenticated ? state : null;
  const order = current?.order ?? null;

  useEffect(() => {
    setState(null);
    setHistory(null);
    paidOrders.current.clear();
    return () => {
      sequence.current += 1;
      request.current?.abort();
      request.current = null;
      historyRequest.current?.abort();
      historyRequest.current = null;
    };
  }, [scope]);

  const close = useCallback(() => {
    sequence.current += 1;
    request.current?.abort();
    request.current = null;
    historyRequest.current?.abort();
    historyRequest.current = null;
    setState(null);
    setHistory(null);
  }, []);

  const create = useCallback(async (payload: CreateBillingOrder) => {
    if (!authenticated || scopeRef.current !== scope || request.current) return;
    const generation = ++sequence.current;
    const controller = new AbortController();
    request.current = controller;
    setState({ scope, order: null, creating: true, error: null });
    const isCurrent = () => scopeRef.current === scope && sequence.current === generation && !controller.signal.aborted;
    try {
      const next = await membershipApi.createOrder(payload, token, controller.signal);
      if (!isCurrent()) return;
      setState({ scope, order: next, creating: false, error: null });
    } catch {
      if (isCurrent()) setState({ scope, order: null, creating: false, error: '订单结果未确认，请先查看订单记录，避免重复创建。' });
    } finally {
      if (request.current === controller) request.current = null;
    }
  }, [authenticated, scope, token]);

  const openHistory = async () => {
    if (!authenticated || scopeRef.current !== scope) return;
    close();
    const controller = new AbortController();
    historyRequest.current = controller;
    setHistory({ scope, orders: [], loading: true, error: null });
    try {
      const result = await membershipApi.getOrders(token, controller.signal);
      if (controller.signal.aborted || scopeRef.current !== scope) return;
      setHistory({ scope, orders: result.orders, loading: false, error: null });
    } catch {
      if (!controller.signal.aborted && scopeRef.current === scope) setHistory({ scope, orders: [], loading: false, error: '订单记录暂未同步，请稍后重试。' });
    } finally {
      if (historyRequest.current === controller) historyRequest.current = null;
    }
  };
  const openOrder = (value: BillingOrder) => {
    if (!authenticated || history?.scope !== scope || !history.orders.some(item => item.id === value.id)) return;
    close();
    setState({ scope, order: value, creating: false, error: null });
  };

  useEffect(() => {
    if (!authenticated || !order || order.status !== 'pending') return;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    let stopped = false;
    const id = order.id;
    const generation = sequence.current;
    const isCurrent = () => !stopped && scopeRef.current === scope && sequence.current === generation;
    const poll = async () => {
      if (!isCurrent()) return;
      if (document.visibilityState !== 'visible') { schedule(); return; }
      controller = new AbortController();
      try {
        const next = await membershipApi.getOrder(id, token, controller.signal);
        if (!isCurrent() || controller.signal.aborted || next.id !== id) return;
        setState({ scope, order: next, creating: false, error: null });
        if (next.status === 'pending') schedule();
      } catch {
        if (!isCurrent() || controller.signal.aborted) return;
        setState(previous => previous?.scope === scope ? { ...previous, error: '订单状态暂未同步，正在重试；请勿重复下单。' } : previous);
        schedule();
      } finally {
        controller = null;
      }
    };
    const schedule = () => { if (isCurrent()) timer = window.setTimeout(() => void poll(), 3000); };
    const foreground = () => {
      if (document.visibilityState !== 'visible' || controller && !controller.signal.aborted) return;
      window.clearTimeout(timer);
      void poll();
    };
    schedule();
    document.addEventListener('visibilitychange', foreground);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      controller?.abort();
      document.removeEventListener('visibilitychange', foreground);
    };
  }, [authenticated, order?.id, order?.status, scope, token]);

  useEffect(() => {
    if (!order || order.status !== 'paid' || paidOrders.current.has(order.id)) return;
    paidOrders.current.add(order.id);
    notifyMembershipChanged();
  }, [order]);

  return { order, creating: current?.creating ?? false, error: current?.error ?? null, create, close, openHistory, openOrder,
    history: history?.scope === scope && authenticated ? history : null };
}
