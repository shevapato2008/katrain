import { membershipErrorCode } from '../membership/presentation';

export type ReportAccessIssue = 'insufficient' | 'verification_required';

export function reportAccessIssueFor(error: unknown): ReportAccessIssue | null {
  if (error && typeof error === 'object' && 'status' in error && error.status === 401) return null;
  const code = membershipErrorCode(error, 'quote_failed');
  return code === 'insufficient' || code === 'verification_required' ? code : null;
}
