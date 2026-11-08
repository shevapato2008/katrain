import { ApiError, authHeaders } from '../api';
import type { BillingOrder, BillingQuote, BillingQuoteRequest, CreateBillingOrder, CreatePositionAnalysis, MembershipCatalog, MembershipUsage, PositionAnalysis } from '../features/membership/types';

async function request<T>(path: string, token: string | null | undefined, signal?: AbortSignal, payload?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: payload === undefined ? 'GET' : 'POST',
    headers: { ...authHeaders(token), ...(payload === undefined ? {} : { 'Content-Type': 'application/json' }) },
    credentials: 'same-origin', cache: 'no-store', signal,
    ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
  });
  if (response.ok) return response.json() as Promise<T>;
  let detail: unknown;
  try { detail = (await response.json() as { detail?: unknown }).detail; } catch { /* A gateway may return HTML. */ }
  const message = typeof detail === 'string' ? detail
    : detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string'
      ? detail.message : `Request failed ${response.status}`;
  throw new ApiError(response.status, message, detail);
}

export const membershipApi = {
  getCatalog: (token?: string | null, signal?: AbortSignal) => request<MembershipCatalog>('/api/v1/billing/catalog', token, signal),
  getUsage: (token?: string | null, signal?: AbortSignal) => request<MembershipUsage>('/api/v1/billing/usage', token, signal),
  createQuote: (payload: BillingQuoteRequest, token?: string | null, signal?: AbortSignal) => request<BillingQuote>('/api/v1/billing/quotes', token, signal, payload),
  createOrder: (payload: CreateBillingOrder, token?: string | null, signal?: AbortSignal) => request<BillingOrder>('/api/v1/billing/orders', token, signal, payload),
  getOrders: (token?: string | null, signal?: AbortSignal) => request<{ orders: BillingOrder[] }>('/api/v1/billing/orders', token, signal),
  getOrder: (id: string, token?: string | null, signal?: AbortSignal) => request<BillingOrder>(`/api/v1/billing/orders/${encodeURIComponent(id)}`, token, signal),
  cancelOrder: (id: string, token?: string | null, signal?: AbortSignal) => request<BillingOrder>(`/api/v1/billing/orders/${encodeURIComponent(id)}/cancel`, token, signal, {}),
  createPosition: (payload: CreatePositionAnalysis, token?: string | null, signal?: AbortSignal) => request<PositionAnalysis>('/api/v1/analysis/positions', token, signal, payload),
  getPosition: (id: string, token?: string | null, signal?: AbortSignal) => request<PositionAnalysis>(`/api/v1/analysis/positions/${encodeURIComponent(id)}`, token, signal),
};
