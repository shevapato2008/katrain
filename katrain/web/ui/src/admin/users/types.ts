export interface AdminUserRow { id: number; username: string; rank: string | null; credits: number; is_admin: boolean; created_at: string | null }
export interface AdminUserList { items: AdminUserRow[]; total: number; page: number; page_size: number }
export interface AdminUserDetail extends AdminUserRow { uuid: string; reserved: { amount: number; count: number }; admin_adjust_total: number }
export interface LedgerRow { id: number; created_at: string | null; reason: string; delta: number; status: 'committed' | 'reserved' | 'refunded' | string; balance_after: number; ref_id: string }
export interface LedgerPage { items: LedgerRow[]; next_before_id: number | null }
export interface QuotaRow { kind: string; period_key: string; allowance: number; used: number }
export interface RedeemedRow { code: string; credits: number; used_at: string | null }
export interface AdjustInput { amount: number; reason: string; idempotency_key: string; confirm_username: string; confirm_amount: number }
export interface AdjustResult { balance: number; transaction_id: number; replayed: boolean }
export interface CodesInput { count: number; credits: number; days: number; note: string; idempotency_key: string }
export interface CodesResult { codes: string[]; count: number; credits: number; expires_at: string }
export interface CodeBatch { created_at: string | null; credits: number; count: number; used: number; expires_at: string | null; note: string | null; created_by: string | null }
export interface CodeRow { code: string; credits: number; expires_at: string | null; state: 'used' | 'unused' | 'expired'; used_by: string | null; used_at: string | null }
export interface CodeListing { batches: CodeBatch[]; codes: CodeRow[] }
export interface AuditRow { id: number; created_at: string | null; actor_username: string; action: string; target_type: string | null; target_id: number | null; target_label: string | null; success: boolean; detail: unknown }
export interface AuditPage { items: AuditRow[]; total: number; page: number; page_size: number }
export interface AuditQuery { action?: string; since?: string; until?: string; target_user_id?: string; page?: number }
