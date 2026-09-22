import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { emphasized } from './emphasized';

/** 断言的是**换算与分支**(哪几段进了 `<b>`),不是布局 —— jsdom 在这件事上有资格作证。 */
describe('emphasized', () => {
  const html = (s: string) => {
    const { container } = render(<p>{emphasized(s)}</p>);
    return container.querySelector('p')!;
  };

  it('把 <b> 包住的那一段渲染成 <b>,其余是文本', () => {
    const p = html('这几项<b>开局后都不能改</b>,自由对弈<b>不计入段位</b>。');
    expect(p.textContent).toBe('这几项开局后都不能改,自由对弈不计入段位。');
    expect([...p.querySelectorAll('b')].map((b) => b.textContent))
      .toEqual(['开局后都不能改', '不计入段位']);
  });

  it('粗体可以放在句首 —— 语序换了也要能表达(这正是拆成片段做不到的那件事)', () => {
    const p = html('<b>Cannot be changed</b> once the game starts.');
    expect(p.querySelector('b')!.textContent).toBe('Cannot be changed');
    expect(p.textContent).toBe('Cannot be changed once the game starts.');
  });

  it('没有标记时原样出一段文本', () => {
    const p = html('就一句话。');
    expect(p.querySelector('b')).toBeNull();
    expect(p.textContent).toBe('就一句话。');
  });

  it('标记不配对时不吞字:多余的标记当字面文本出现', () => {
    expect(html('缺闭合<b>一半').textContent).toBe('缺闭合一半');
    expect(html('多一个</b>闭合').textContent).toBe('多一个</b>闭合');
    expect(html('嵌套<b>外<b>内</b>').textContent).toBe('嵌套外<b>内');
  });

  it('译文里的尖括号和 & 当字面文本,不当标记 —— 这条路不能是注入面', () => {
    const p = html('比较 <script>alert(1)</script> 与 a&b');
    expect(p.textContent).toBe('比较 <script>alert(1)</script> 与 a&b');
    expect(p.querySelector('script')).toBeNull();
  });
});
