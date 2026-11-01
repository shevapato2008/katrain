/** Prices and entitlements come from the server catalog. Units stay inside the API boundary. */
export type MembershipProfile = 'normal' | 'advanced';
export type MembershipPlanCode = 'plus' | 'pro' | 'max';
export type MembershipMode = 'legacy' | 'enabled' | 'paused';
export type PaymentsMode = 'disabled' | 'mock' | 'live';
export type BillingSource = 'membership' | 'wallet' | 'free_report' | 'owned';

export interface MembershipCapabilities {
  membership: boolean;
  usage: boolean;
  quotes: boolean;
  positions: boolean;
  orders: boolean;
  can_claim_free_report: boolean;
  reason?: string;
}

export interface MembershipPlan {
  code: MembershipPlanCode;
  name: string;
  amount_fen: number;
  term_days: number;
  term_units: number;
  week_units: number;
  term_report_reference: number;
  week_report_reference: number;
  full_use_savings_percent: number;
  sale_enabled: boolean;
}

export interface MembershipCatalog {
  catalog_version: string;
  server_now: string;
  environment: string;
  membership_mode: MembershipMode;
  capabilities: MembershipCapabilities;
  payments_mode: PaymentsMode;
  plans: MembershipPlan[];
  topups: Array<{ sku: string; amount_fen: number; credits: number; display_points: string }>;
  profiles: Record<MembershipProfile, { visits: number; credits_per_position: number; display_points_per_position: string }>;
}

export interface MembershipPeriod {
  limit: number;
  used: number;
  reserved: number;
  remaining: number;
  percent: number;
  reset_at: string;
}

export interface MembershipTerm {
  code: MembershipPlanCode;
  name: string;
  starts_at: string;
  ends_at: string;
}

export interface MembershipUsage {
  catalog_version: string;
  server_now: string;
  revision: number;
  environment: string;
  capabilities: MembershipCapabilities;
  payments_mode: PaymentsMode;
  plan: { current: MembershipTerm | null; next: MembershipTerm | null };
  term: MembershipPeriod | null;
  week: MembershipPeriod | null;
  wallet: { credits: number; display_points: string } | null;
  free: { eligible: boolean; remaining: number; limit: number; reset_at: string; reason: string | null } | null;
}

export interface BillingQuoteRequest {
  kind: 'report' | 'position';
  profile: MembershipProfile;
  sgf?: string;
  game_id?: string;
  session_id?: string;
}

export interface BillingQuote {
  token: string;
  catalog_version: string;
  environment: string;
  kind: 'report' | 'position';
  profile: MembershipProfile;
  units: number;
  wallet_max_credits: number;
  wallet_max_display_points: string;
  source_policy: 'membership_then_wallet';
  source: BillingSource;
  expires_at: string;
  server_now: string;
  fingerprint: string;
}

export interface CreateBillingOrder {
  sku: 'membership_plus' | 'membership_pro' | 'membership_max' | 'topup_10' | 'topup_30' | 'topup_100';
  provider?: 'mock' | 'live';
  idempotency_key: string;
}

export interface BillingOrder {
  id: string;
  sku: CreateBillingOrder['sku'];
  kind: 'membership' | 'topup';
  status: 'pending' | 'paid' | 'expired' | 'failed' | 'refunded';
  amount_fen: number;
  currency: 'CNY';
  payments_mode: PaymentsMode;
  provider: 'mock' | 'live';
  created_at: string;
  expires_at: string;
  paid_at: string | null;
  fulfillment: { credits?: number; display_points?: string; plan_code?: MembershipPlanCode; starts_at?: string; ends_at?: string } | null;
  payment_url?: string | null;
  estimated_starts_at?: string | null;
  estimated_ends_at?: string | null;
}

export interface CreatePositionAnalysis {
  profile: MembershipProfile;
  sgf?: string;
  game_id?: string;
  session_id?: string;
  quote_token: string;
  idempotency_key: string;
}

export interface PositionAnalysis {
  operation_id: string | number;
  state: 'reserved' | 'running' | 'succeeded' | 'failed' | 'refunded' | 'result_expired';
  source: BillingSource;
  profile: MembershipProfile;
  units: number;
  wallet_credits: number;
  catalog_version: string;
  result?: { ownership: number[]; moves: Array<{ move: string; visits: number; winrate: number; score_lead: number; pv?: string[] }>; rootInfo?: { visits: number; winrate: number; scoreLead: number } };
  error?: { code: string; message: string };
  revision?: number;
}
