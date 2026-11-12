export function publicUsernameError(value: string): 'invalid_public_username' | 'reserved_public_username' | null {
  if (Array.from(value).length < 2 || Array.from(value).length > 24 || !/^[\p{L}\p{N}_-]+$/u.test(value)) return 'invalid_public_username';
  if (/^(?:guest|admin)$/i.test(value) || /^(?:admin:|u_)/i.test(value)) return 'reserved_public_username';
  return null;
}

export function newPasswordValid(value: string): boolean {
  return Array.from(value).length >= 15 && new TextEncoder().encode(value).length <= 72 && !value.includes('\0');
}
