import { describe, it, expect } from 'vitest';
import { spaceCjkLatin } from './cjkSpace';

describe('spaceCjkLatin', () => {
  it('中文接拉丁:插一个空格', () => {
    expect(spaceCjkLatin('登录OGS')).toBe('登录 OGS');
  });

  it('拉丁接中文:插一个空格', () => {
    expect(spaceCjkLatin('OGS登录')).toBe('OGS 登录');
  });

  it('纯中文:不动', () => {
    expect(spaceCjkLatin('登录星阵')).toBe('登录星阵');
  });

  it('纯拉丁:不动', () => {
    expect(spaceCjkLatin('Sign in to OGS')).toBe('Sign in to OGS');
  });
});
