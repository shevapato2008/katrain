import { useEffect, useRef, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { AdminApiError } from '../api/client';

export const REASON_LABELS: Record<string, string> = {
  admin_adjust: '后台调整', admin_grant: '后台发放', redeem: '兑换码', order: '充值订单', signup_grant: '注册赠送',
  report: '复盘预扣', analysis_territory: '形势判断', hints: '提示', variations: '变化图', territory: '形势判断',
};
export const ACTION_LABELS: Record<string, string> = {
  credit_adjust: '积分调整', redeem_codes_generate: '生成兑换码', login_success: '登录', login_failed: '登录失败', logout: '退出',
  tutorial_figure_update: '教程修改', tutorial_figure_review: '教程审核',
};

const shanghai = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
export function when(iso: string | null | undefined, dateOnly = false): string {
  if (!iso) return '—';
  const parts = Object.fromEntries(shanghai.formatToParts(new Date(iso)).map((part) => [part.type, part.value]));
  return dateOnly ? `${parts.year}-${parts.month}-${parts.day}` : `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`;
}
export const newKey = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}${Math.random()}`).replace(/[^0-9a-f]/gi, '').toLowerCase().padEnd(32, '0').slice(0, 32);

/** Classifies a failed read: 401 goes back to login, 403 is shown as no permission, anything else is retryable. */
export function describe(cause: unknown): { status: number; message: string } {
  if (cause instanceof AdminApiError) return { status: cause.status, message: cause.status === 403 ? '当前后台账号没有权限查看这部分数据。' : cause.message };
  return { status: 0, message: cause instanceof Error ? cause.message : '请求失败，请重试。' };
}

export function LoadError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="lab-banner bad" role="alert"><AlertTriangle aria-hidden="true" /><span>{message}</span>{onRetry && <button className="lab-btn small" type="button" onClick={onRetry}><RefreshCw aria-hidden="true" />重试</button>}</div>;
}

export function Dialog({ label, title, children, actions, onClose, closable = true }: { label: string; title: ReactNode; children: ReactNode; actions: ReactNode; onClose: () => void; closable?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    dialog.showModal();
    return () => { dialog.close(); };
  }, []);
  return <dialog ref={ref} className="ub-dialog" aria-label={label} onCancel={(event) => { event.preventDefault(); if (closable) onClose(); }}>
    <h2>{title}</h2>
    {children}
    <div className="ub-dialog-actions">{actions}</div>
  </dialog>;
}
