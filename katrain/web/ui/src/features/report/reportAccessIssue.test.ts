import { describe, expect, it } from 'vitest';
import { reportAccessIssueFor } from './reportAccessIssue';

describe('reportAccessIssueFor', () => {
  it.each([
    [{ status: 402 }, 'insufficient'],
    [{ status: 402, detail: { code: 'insufficient_credits' } }, 'insufficient'],
    [{ detail: { code: 'insufficient_credits' } }, 'insufficient'],
    [{ status: 403, detail: { code: 'verification_required' } }, 'verification_required'],
    [{ status: 403, body: JSON.stringify({ detail: { code: 'verification_required' } }) }, 'verification_required'],
  ])('classifies recognized report access failures: %j', (error, expected) => {
    expect(reportAccessIssueFor(error)).toBe(expected);
  });

  it.each([
    { status: 401 },
    { status: 401, detail: { code: 'verification_required' } },
    { status: 401, detail: { code: 'insufficient_credits' } },
    { status: 503 },
    { status: 403, detail: { code: 'unknown' } },
    { detail: { code: 'quote_mismatch' } },
    new Error('报告额度不足'),
    { balance: 0 },
    null,
    undefined,
  ])('keeps unrelated failures out of access guidance: %j', (error) => {
    expect(reportAccessIssueFor(error)).toBeNull();
  });
});
