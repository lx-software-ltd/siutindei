import { homeWizardChoices } from './choices';

// Map markers swap /images/categories/ for /images/markers/, so every
// path here needs a marker twin.
const ACTIVITY_ICON_SRC: Record<string, string> = {
  'baby-toddler': '/images/categories/early-years.svg',
  sports: '/images/categories/sports.svg',
  water: '/images/categories/play.svg',
  art: '/images/categories/arts.svg',
  performing: '/images/categories/arts.svg',
  languages: '/images/categories/learning.svg',
  stem: '/images/categories/learning.svg',
  tutoring: '/images/categories/learning.svg',
  community: '/images/categories/community.svg',
};

export const DEFAULT_ACTIVITY_ICON_SRC = '/images/categories/class.svg';

export const KIND_ICON_SRC: Record<string, string> = {
  class: '/images/categories/class.svg',
  camp: '/images/categories/workshop.svg',
  place: '/images/categories/outdoor.svg',
  eat: '/images/categories/indoor.svg',
};

export const WEEKEND_ICON_SRC = '/images/categories/play.svg';

export const AGE_ICON_SRC: Record<string, string> = {
  '0-1': '/images/ages/baby.png',
  '1-2': '/images/ages/baby.png',
  '3-5': '/images/ages/toddler.png',
  '6-11': '/images/ages/child.png',
  '12-18': '/images/ages/child.png',
};

export const REGION_ICON_SRC: Record<string, string> = {
  hong_kong_island: '/images/regions/hong-kong-island.svg',
  kowloon: '/images/regions/kowloon.svg',
  new_territories: '/images/regions/new-territories.svg',
  islands: '/images/regions/islands.svg',
};

export const ALL_HONG_KONG_ICON_SRC = '/images/flags/hong-kong.svg';

export const REGION_ROW_ORDER = [
  'hong_kong_island',
  'kowloon',
  'new_territories',
  'islands',
] as const;

export function iconSrcForActivity(typeId: string): string {
  return ACTIVITY_ICON_SRC[typeId] ?? DEFAULT_ACTIVITY_ICON_SRC;
}

export function activityTypeIdForCategory(
  categoryId: string | null,
): string {
  if (!categoryId) {
    return '';
  }
  const match = homeWizardChoices.activityTypes.find(
    (type) => type.categoryId === categoryId,
  );
  return match?.id ?? '';
}

export function iconSrcForActivityCategory(
  categoryId: string | null,
): string {
  return iconSrcForActivity(activityTypeIdForCategory(categoryId));
}

export function iconSrcForKind(kindId: string): string {
  return KIND_ICON_SRC[kindId] ?? DEFAULT_ACTIVITY_ICON_SRC;
}

export function iconSrcForAge(ageGroupId: string): string | undefined {
  return AGE_ICON_SRC[ageGroupId];
}

export function iconSrcForRegion(regionId: string): string | undefined {
  return REGION_ICON_SRC[regionId];
}
