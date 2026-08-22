import type { ReactNode } from 'react';
import ModulePlate from './ModulePlate';

interface ContentPageHeaderProps {
  title: ReactNode;
  /**
   * 上一级页面的简称（「对局」「死活题」「教程」…）。**不上屏**，只用来把返回键的
   * 无障碍名从泛泛的「返回」变成「返回对局」。省略时按根级页面处理。
   */
  parentLabel?: string;
  /** 上一级页面的路由。省略 = 这是根级页面，不画返回键（spec §2.4）。 */
  parentTo?: string;
  /**
   * 最右侧的单个状态件（一个进度 Chip 之类）。
   *
   * spec §2.4 说「状态放最右」，同一段又禁止把「状态说明和 chip **堆**进页头」——
   * 允许的是一个状态件，不是一排。这里刻意只留一个插槽，堆不进来。
   */
  status?: ReactNode;
}

/**
 * 无棋盘内容页顶端的页头：左上角返回箭头图标键 + 标题 + 状态。
 *
 * 结构与棋盘页右栏的模块牌**完全同一份实现**（`ModulePlate`，只是 `size="page"`
 * 换了字号档），这是 spec §2.4「无棋盘内容页把同一结构放在内容区顶端」的直译。
 *
 * 2026-08-22 之前这里是「标题在左 + 右侧一个带文字的 outlined 返回按钮」。冻结原型的
 * `cph()` 至今还画着那个旧形状 —— 它没跟上 Fan 当日「返回按钮都放到右边栏的左上角吧。
 * 不止限于复盘页面」的裁定（`plate iconleft` 跟上了）。规范权威高于原型，按规范。
 *
 * **没有 `subtitle` 属性是故意的**：规范禁止把长副标题堆进页头，副标要下沉到正文第一个
 * 业务区。属性不存在，就没有调用方能把它塞回来 —— 闸建在类型上，比写在注释里可靠。
 */
const ContentPageHeader = ({ title, parentLabel, parentTo, status }: ContentPageHeaderProps) => (
  <ModulePlate
    size="page"
    title={title}
    status={status}
    showBack={Boolean(parentTo)}
    backTo={parentTo ?? ''}
    backLabel={parentLabel}
  />
);

export default ContentPageHeader;
