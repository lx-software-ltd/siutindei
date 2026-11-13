import enContent from '@/content/en.json';
import zhHKContent from '@/content/zh-HK.json';
import type { WizardLabels } from '@/lib/home-wizard/choices';

import type { ListingKind } from './types';

export type KindPageSlug = keyof typeof enContent.activitiesPage.kindPages;

export interface KindPage {
  /** The `/activities/{slug}` segment. */
  readonly slug: KindPageSlug;
  readonly kind: ListingKind;
  readonly labels: WizardLabels;
}

const KIND_BY_SLUG: Readonly<Record<KindPageSlug, ListingKind>> = {
  classes: 'class',
  camps: 'camp',
  places: 'place',
  nurseries: 'preschool',
};

/** Hub order: the three the hub lists, then nurseries, which it only links. */
export const KIND_PAGES: readonly KindPage[] = (
  ['classes', 'camps', 'places', 'nurseries'] as const
).map((slug) => ({
  slug,
  kind: KIND_BY_SLUG[slug],
  labels: {
    en: enContent.activitiesPage.kindPages[slug],
    'zh-HK': zhHKContent.activitiesPage.kindPages[slug],
  },
}));

/** Kinds the hub groups its listings under. */
export const HUB_SECTION_KINDS: ReadonlySet<ListingKind> = new Set(['class', 'camp', 'place']);

export function kindPageForKind(kind: ListingKind): KindPage | undefined {
  return KIND_PAGES.find((page) => page.kind === kind);
}
