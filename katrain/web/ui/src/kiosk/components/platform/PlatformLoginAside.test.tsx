import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlatformLoginAside } from './PlatformLoginAside';
import { LOGIN_FACTS } from '../../constants/platformLoginFacts';

/**
 * Task 5 Step 6b。`LOGIN_FACTS[platform]` 是**变量**传给 `t()` 的
 * (`t(f.titleKey, f.titleZh)`),`test_kiosk_i18n.py` 的通用正则(只认两个单引号字面量)
 * 看不见这几条调用 —— 那条闸只能证明「目录里有条目」,证不了「组件真的走了 t()」。
 * 组件若直接渲染 `f.titleZh`、或漏了某一条 `t(f.bodyKey, ...)`,那条闸照样全绿。
 *
 * R-24:`i18n.__setTranslationsForTest` 不存在(`translations` 是 `private`,没有测试注入口,
 * 不为了测试往生产类上加方法)。改成 mock 掉 `useTranslation` hook —— 效果等价:
 * **查得到就不该看见中文兜底**。`i18n.ts` 的实现是 `translations[key] || defaultText || key`,
 * 装一张「查得到」的韩文表进去,屏上还出现 `titleZh`/`bodyZh` 就说明那一条没走 `t()`。
 */
const FAKE: Record<string, string> = {};
for (const facts of Object.values(LOGIN_FACTS)) {
  for (const f of facts) {
    FAKE[f.titleKey] = `KO:${f.titleKey}`;
    FAKE[f.bodyKey] = `KO:${f.bodyKey}`;
  }
}
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (k: string, d?: string) => FAKE[k] ?? d ?? k, lang: 'ko' }),
}));

describe('PlatformLoginAside · 装着韩文表时不许看见中文兜底', () => {
  it('星阵左栏每一条都是韩文,不是中文兜底', () => {
    render(<PlatformLoginAside platform="golaxy" />);
    for (const f of LOGIN_FACTS.golaxy) {
      expect(screen.getByText(`KO:${f.titleKey}`)).toBeInTheDocument();
      expect(screen.queryByText(f.titleZh)).toBeNull();
      expect(screen.getByText(`KO:${f.bodyKey}`)).toBeInTheDocument();
      expect(screen.queryByText(f.bodyZh)).toBeNull();
    }
  });

  it('OGS 左栏每一条都是韩文,不是中文兜底', () => {
    render(<PlatformLoginAside platform="ogs" />);
    for (const f of LOGIN_FACTS.ogs) {
      expect(screen.getByText(`KO:${f.titleKey}`)).toBeInTheDocument();
      expect(screen.queryByText(f.titleZh)).toBeNull();
      expect(screen.getByText(`KO:${f.bodyKey}`)).toBeInTheDocument();
      expect(screen.queryByText(f.bodyZh)).toBeNull();
    }
  });
});
