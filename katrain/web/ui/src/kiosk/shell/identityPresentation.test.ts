import { describe, expect, test } from 'vitest';
import { identityPresentation } from './identityPresentation';

describe('identityPresentation', () => {
  test('没登录显示「访客」,头像首字是「访」', () => {
    expect(identityPresentation({})).toEqual({ avatar: '访', label: '访客' });
  });

  test('登录了取用户名首字', () => {
    expect(identityPresentation({ username: '张三' })).toEqual({ avatar: '张', label: '张三' });
  });

  test('拉丁名首字母大写 —— 头像格是 12px,小写字母在圆里偏下', () => {
    expect(identityPresentation({ username: 'frank' })).toEqual({ avatar: 'F', label: 'frank' });
  });

  test('空串按没登录处理 —— 空头像圈比「访」更没信息', () => {
    expect(identityPresentation({ username: '' })).toEqual({ avatar: '访', label: '访客' });
  });

  test('只有空白也按没登录处理', () => {
    expect(identityPresentation({ username: '   ' })).toEqual({ avatar: '访', label: '访客' });
  });

  test('首字是代理对时不许劈成半个码元', () => {
    // '𠮷' 是 U+20BB7,UTF-16 两个码元。`name[0]` 会切出半个,渲染成 �。
    expect(identityPresentation({ username: '𠮷田' }).avatar).toBe('𠮷');
  });
});
