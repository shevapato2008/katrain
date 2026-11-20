interface AccountName { username?: string | null; public_username?: string | null; }
const internalHandle = /^u_[0-9a-f]{20}$/i;
const uuid = /^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i;
const fullPhone = /^(?:(?:\+|00)?86)?1[3-9]\d{9}$/;

// Presentation only. Authorization, API parameters and storage keep canonical identity.
export function displayAccountName(user: AccountName | null | undefined, fallback: string): string {
  for (const value of [user?.public_username, user?.username]) {
    const name = value?.trim();
    if (name && !internalHandle.test(name) && !uuid.test(name) && !fullPhone.test(name.replace(/[\s()-]/g, ''))) return name;
  }
  return fallback;
}

// Only a server-resolved account seat carries user_id/public_username. An SGF or platform
// player name is independent of the signed-in account, even if the names happen to match.
export function displayPlayerName(
  player: { name?: string | null; user_id?: number | string | null; public_username?: string | null },
  fallback: string,
): string {
  if (typeof player.user_id === 'number' || player.public_username !== undefined) {
    return displayAccountName({ username: player.name, public_username: player.public_username }, fallback);
  }
  return player.name || fallback;
}

export function displayGamePlayerName(
  game: { player_black?: string | null; player_white?: string | null; display_player_black?: string | null; display_player_white?: string | null },
  color: 'B' | 'W',
  fallback: string,
): string {
  const display = color === 'B' ? game.display_player_black : game.display_player_white;
  const original = color === 'B' ? game.player_black : game.player_white;
  return (display ?? original) || fallback;
}
