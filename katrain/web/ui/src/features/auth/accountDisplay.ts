interface AccountName { username?: string | null; public_username?: string | null; }
const internalHandle = /^u_[0-9a-f]{20}$/i;

// Presentation only. Authorization, API parameters and storage keep canonical identity.
export function displayAccountName(user: AccountName | null | undefined, fallback: string): string {
  for (const value of [user?.public_username, user?.username]) {
    const name = value?.trim();
    if (name && !internalHandle.test(name)) return name;
  }
  return fallback;
}
