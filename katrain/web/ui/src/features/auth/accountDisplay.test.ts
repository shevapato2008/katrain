import { expect, it } from 'vitest';
import { displayAccountName, displayPlayerName, displayGamePlayerName } from './accountDisplay';

it('prefers public name, falls back to legacy names, and hides internal handles', () => {
  expect(displayAccountName({ username: 'u_0123456789abcdefabcd', public_username: '公开棋手' }, 'Account')).toBe('公开棋手');
  expect(displayAccountName({ username: 'old-player', public_username: null }, 'Account')).toBe('old-player');
  expect(displayAccountName({ username: 'u_0123456789abcdefabcd' }, 'Account')).toBe('Account');
  expect(displayAccountName({ username: 'u_0123456789abcdefabcd', public_username: 'u_aaaaaaaaaaaaaaaaaaaa' }, 'Account')).toBe('Account');
});

it('never uses UUIDs or full phone numbers as account labels', () => {
  for (const username of ['cce0f02b-36f3-4ae5-813e-101c73fe7830', '+8613800138000', '13800138000']) {
    expect(displayAccountName({ username }, '账号')).toBe('账号');
  }
});

it('uses trusted seat public names without changing their canonical identity', () => {
  const seat = { user_id: 7, name: 'u_0123456789abcdefabcd', public_username: '公开棋手' };
  expect(displayPlayerName(seat, '账号')).toBe('公开棋手');
  expect(seat.name).toBe('u_0123456789abcdefabcd');
  expect(displayPlayerName({ user_id: 8, name: 'u_aaaaaaaaaaaaaaaaaaaa' }, '账号')).toBe('账号');
  expect(displayPlayerName({ user_id: 9, name: 'old-player' }, '账号')).toBe('old-player');
});

it('does not replace imported or platform names with account names', () => {
  expect(displayPlayerName({ name: '外部棋手' }, '账号')).toBe('外部棋手');
  expect(displayPlayerName({ name: 'u_0123456789abcdefabcd' }, '账号')).toBe('u_0123456789abcdefabcd');
});

it('reads historical game display fields while preserving names used by ownership comparisons', () => {
  const game = { player_black: 'u_0123456789abcdefabcd', player_white: 'KataGo', display_player_black: '公开棋手' };
  expect(displayGamePlayerName(game, 'B', '黑方')).toBe('公开棋手');
  expect(displayGamePlayerName(game, 'W', '白方')).toBe('KataGo');
  expect(game.player_black).toBe('u_0123456789abcdefabcd');
  expect(displayGamePlayerName({ ...game, display_player_black: '' }, 'B', '账号')).toBe('账号');
});

it('does not retain another account label after account switch or guest signout', () => {
  const first = { username: 'u_0123456789abcdefabcd', public_username: '第一位' };
  const second = { username: 'u_aaaaaaaaaaaaaaaaaaaa', public_username: '第二位' };
  expect(displayAccountName(first, '账号')).toBe('第一位');
  expect(displayAccountName(second, '账号')).toBe('第二位');
  expect(displayAccountName(null, '访客')).toBe('访客');
  expect(displayAccountName({ username: 'guest' }, '访客')).toBe('guest');
});
