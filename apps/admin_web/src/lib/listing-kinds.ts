import type { components } from '../types/api-admin.generated';

export type ListingKind = components['schemas']['ListingKind'];
export type ListingFacts = Record<string, boolean>;

export const DEFAULT_LISTING_KIND: ListingKind = 'class';

export const LISTING_KIND_OPTIONS: { value: ListingKind; label: string }[] = [
  { value: 'class', label: 'Classes and clubs' },
  { value: 'camp', label: 'Camps and workshops' },
  { value: 'place', label: 'Places to play' },
  { value: 'preschool', label: 'Nurseries and kindergartens' },
  { value: 'eat', label: 'Eat with kids' },
];

const CLASS_FACTS = ['drop_in', 'parent_stays', 'sen_friendly'];

/** Mirrors `FACT_KEYS` in `backend/src/app/services/listing_kinds.py`. */
export const FACT_KEYS: Record<ListingKind, string[]> = {
  class: CLASS_FACTS,
  camp: [...CLASS_FACTS, 'lunch_included'],
  place: [
    'toilets',
    'changing_table',
    'shade',
    'fenced',
    'stroller_access',
    'water_play',
    'lifeguard',
    'parking',
    'food_nearby',
  ],
  preschool: [],
  eat: [
    'high_chairs',
    'kids_menu',
    'changing_table',
    'stroller_access',
    'room_to_run',
    'outdoor_seating',
  ],
};

export const FACT_LABELS: Record<string, string> = {
  drop_in: 'Drop-in',
  parent_stays: 'Parent stays',
  sen_friendly: 'SEN-friendly',
  lunch_included: 'Lunch included',
  toilets: 'Toilets',
  changing_table: 'Changing table',
  shade: 'Shade',
  fenced: 'Fenced',
  stroller_access: 'Stroller access',
  water_play: 'Water play',
  lifeguard: 'Lifeguard',
  parking: 'Parking',
  food_nearby: 'Food nearby',
  high_chairs: 'High chairs',
  kids_menu: "Kids' menu",
  room_to_run: 'Room to run',
  outdoor_seating: 'Outdoor seating',
};

export function isListingKind(value: unknown): value is ListingKind {
  return (
    typeof value === 'string' &&
    LISTING_KIND_OPTIONS.some((option) => option.value === value)
  );
}

export function listingKindLabel(value: unknown): string | null {
  return LISTING_KIND_OPTIONS.find((option) => option.value === value)?.label ?? null;
}

/** Boolean facts from an API value, without keys the kind does not allow. */
export function factsForKind(kind: ListingKind, facts: unknown): ListingFacts {
  if (!facts || typeof facts !== 'object' || Array.isArray(facts)) {
    return {};
  }
  const allowed = FACT_KEYS[kind];
  const next: ListingFacts = {};
  for (const [key, value] of Object.entries(facts as Record<string, unknown>)) {
    if (allowed.includes(key) && typeof value === 'boolean') {
      next[key] = value;
    }
  }
  return next;
}

/** `true` seen, `false` seen missing, `undefined` not checked. */
export function setFact(
  facts: ListingFacts,
  key: string,
  value: boolean | undefined
): ListingFacts {
  const next = { ...facts };
  if (value === undefined) {
    delete next[key];
  } else {
    next[key] = value;
  }
  return next;
}

export function factsSummary(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return 'Not checked';
  }
  const parts = Object.entries(value as Record<string, unknown>)
    .filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean')
    .map(([key, seen]) => `${FACT_LABELS[key] ?? key}: ${seen ? 'yes' : 'no'}`);
  return parts.length > 0 ? parts.join(', ') : 'Not checked';
}

/** Mirrors `FIXED_ROOT_KINDS` in `backend/src/app/db/models/category_suggestion.py`. */
const ROOT_ROLE_KINDS: Record<string, ListingKind> = {
  places: 'place',
  nurseries: 'preschool',
  eat: 'eat',
};

/** Mirrors `TOPIC_KINDS` in `backend/src/app/services/listing_kinds.py`. */
export const TOPIC_KINDS: ListingKind[] = ['class', 'camp'];

export interface CategoryKindRoot {
  system_role?: string | null;
  show_in_wizard?: boolean;
}

export type CategoryKindRule =
  | { fixed: ListingKind }
  | { allowed: ListingKind[] }
  | null;

/** What a category's root says about the kind, as the backend applies it. */
export function categoryKindRule(
  root: CategoryKindRoot | null | undefined
): CategoryKindRule {
  if (!root) {
    return null;
  }
  const fixed = root.system_role ? ROOT_ROLE_KINDS[root.system_role] : undefined;
  if (fixed) {
    return { fixed };
  }
  if (root.show_in_wizard) {
    return { allowed: TOPIC_KINDS };
  }
  return null;
}

export function kindForCategoryRule(
  rule: CategoryKindRule,
  current: ListingKind
): ListingKind {
  if (!rule) {
    return current;
  }
  if ('fixed' in rule) {
    return rule.fixed;
  }
  return rule.allowed.includes(current) ? current : DEFAULT_LISTING_KIND;
}
