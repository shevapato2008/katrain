/**
 * Router `state` passed when navigating into a tutorial section, so the section
 * page can render a complete breadcrumb and known book slug on the normal click
 * path. All fields optional: on refresh / deep-link the state is absent and the
 * section page degrades gracefully (slug parsed from figures, breadcrumb shortened).
 *
 * Note: `hasVideo` here comes from the chapter→sections endpoint (reliable);
 * the section-detail endpoint's has_video is NOT reliable and must not gate video.
 */
export interface SectionNavState {
  bookId?: number;
  /**
   * 书所在的分类 slug。2026-08-24 屏 24/25 合屏时加的:屏 25 的「← 目录」要回到
   * `tutorial/{category}?book={id}`,而 `bookId` 一个人指不出那条地址 ——
   * 分类不在书的返回体里能省一次请求的位置上(`TutorialBookDetail.category` 有,
   * 但屏 25 不拉书)。缺了就退回 `/kiosk/tutorial`,不猜。
   */
  category?: string;
  /**
   * 离开时摊开的是哪一章。屏 25 的「← 目录」拿它回到 `?book=…&ch=…` ——
   * 上一版那一屏是「每一章都摊开」的,回来时全收起等于让人重新找一遍自己在哪。
   */
  chapterId?: number;
  /** 章号(「第 3 章」)。屏 25 的页控条标题按稿子写「第 3 章 · 第 2 节 禁入点」。 */
  chapterNumber?: string;
  bookTitle?: string;
  bookSlug?: string;
  chapterTitle?: string;
  sectionTitle?: string;
  hasVideo?: boolean;
}
