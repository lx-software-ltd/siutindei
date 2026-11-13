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
