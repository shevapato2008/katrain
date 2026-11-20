import { expect, it } from 'vitest';
import { newPasswordValid, publicUsernameError } from './namedSignupValidation';

it('counts username code points and reserves internal and system names', () => {
  expect(publicUsernameError('𠮷'.repeat(24))).toBeNull();
  expect(publicUsernameError('𠮷'.repeat(25))).toBe('invalid_public_username');
  expect(publicUsernameError('棋')).toBe('invalid_public_username');
  for (const name of ['Guest', 'admin', 'u_用户', 'admin:fan']) expect(publicUsernameError(name)).not.toBeNull();
  expect(publicUsernameError('棋手_1-𠮷')).toBeNull();
});

it('requires 15 password code points, 72 UTF-8 bytes, retains spaces and rejects NUL', () => {
  expect(newPasswordValid('𠮷'.repeat(14))).toBe(false);
  expect(newPasswordValid('𠮷'.repeat(15))).toBe(true);
  expect(newPasswordValid('中'.repeat(24))).toBe(true);
  expect(newPasswordValid('中'.repeat(25))).toBe(false);
  expect(newPasswordValid(' 1234567890123 ')).toBe(true);
  expect(newPasswordValid('fifteen\0characters')).toBe(false);
});
