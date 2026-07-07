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
  bookTitle?: string;
  bookSlug?: string;
  chapterTitle?: string;
  sectionTitle?: string;
  hasVideo?: boolean;
}
