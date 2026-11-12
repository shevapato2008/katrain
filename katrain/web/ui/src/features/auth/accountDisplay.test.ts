import { expect, it } from 'vitest';
import { displayAccountName } from './accountDisplay';

it('prefers public name, falls back to legacy names, and hides internal handles', () => {
  expect(displayAccountName({ username: 'u_0123456789abcdefabcd', public_username: '公开棋手' }, 'Account')).toBe('公开棋手');
  expect(displayAccountName({ username: 'old-player', public_username: null }, 'Account')).toBe('old-player');
  expect(displayAccountName({ username: 'u_0123456789abcdefabcd' }, 'Account')).toBe('Account');
  expect(displayAccountName({ username: 'u_0123456789abcdefabcd', public_username: 'u_aaaaaaaaaaaaaaaaaaaa' }, 'Account')).toBe('Account');
});
