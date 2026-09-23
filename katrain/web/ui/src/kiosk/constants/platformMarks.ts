import type { CardMark } from '../shell/KioskCard';
import golaxyMark from '../assets/platform-marks/golaxy.png';
import ogsMark from '../assets/platform-marks/ogs.svg';
import foxMark from '../assets/platform-marks/fox.png';

/**
 * 三家外部平台的品牌标记。素材来源、处理方式、以及 OGS 为什么用黑白棋子版而不是官网
 * 首页那个蓝黄圆，全部写在 `../assets/platform-marks/README.md` 里 —— **改这张表之前先读它**。
 *
 * ## 这些不是我们的图标
 *
 * 原先这三处画的是 `globe-hemisphere-west`。那从来不是品牌图标，是**类别**图标，
 * 意思是「互联网上某处」。整套 Phosphor 图标（`currentColor`、染成 accent）说的是
 * 「**这台盒子会做这件事**」；而这三张卡按下去意味着**离开** —— 去别人家下棋。
 * 换成真标记不只是好看，是把「你要出门了」这件事画出来。
 *
 * ⇒ 所以它们**不染色、不进图标目录、不进 MANIFEST**，衬也换了语气（底沉到 `--ink`、
 * 描边退回中性 `--hair`），从「我们画的图标底衬」变成「放外来物的凹槽」。几何一个字没动。
 *
 * ## 查不到就回落，不抛
 *
 * 平台列表是服务端 `/platforms` 下发的，多返回一家我们没有标记的平台是正常事件。
 * `Icon` 缺图标会抛（对我们自己的图标是对的：少一个是 bug），但照搬到这里，
 * 服务端多一行就能把首页打白。调用方查不到时回落到地球 + 保留 accent 染色 ——
 * 那正好诚实地说「一个网上的平台，我们没有它的标记」。
 */
export const PLATFORM_MARKS: Record<string, CardMark> = {
  // 星座自带方形构图（官方文件里左边就是裁掉一半的），满幅铺满衬、由衬切圆角，
  // 那道裁切才读得出是「一片裁到边的星空」而不是渲染坏了。
  golaxy: { src: golaxyMark },
  // 圆形实心标记：居中缩小 + 一圈极细的浅色环。没有那圈环，棋子黑的那半会直接
  // 融进深色衬，屏上只剩一个白色半圆 —— 读起来像月亮不像棋子。
  ogs: { src: ogsMark, disc: true },
  // 官方 iOS 应用图标，自带深色方底，满幅。
  fox: { src: foxMark },
};

export default PLATFORM_MARKS;
