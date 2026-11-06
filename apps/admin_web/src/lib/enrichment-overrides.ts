import type {
  EnrichmentBlocker,
  EnrichmentOverride,
  EnrichmentProposal,
  EnrichmentRead,
} from './api-client-enrichment';

const pricingTypes = new Set([
  'per_class',
  'per_sessions',
  'per_hour',
  'per_day',
  'free',
  'per_month',
  'per_year',
]);

const PRICE_ACTIVITY = 'Pick the activity this price belongs to';
const PRICE_VENUE = 'Pick a venue for this price';
const SCHEDULE_ACTIVITY = 'Pick the activity this schedule belongs to';
const SCHEDULE_VENUE = 'Pick a venue for this schedule';

export interface BlockerContext {
  proposals: EnrichmentProposal[];
  selected: string[];
  venues?: EnrichmentRead['venues'];
  activities?: EnrichmentRead['activities'];
}

/** A whole class count greater than zero. `8.5` and `1e1` are not one. */
export function positiveSessions(value: unknown): number | undefined {
  if (typeof value === 'boolean' || value == null || value === '') {
    return undefined;
  }
  if (typeof value === 'number') {
    if (!Number.isInteger(value) || value <= 0) {
      return undefined;
    }
    return value;
  }
  if (typeof value !== 'string') {
    return undefined;
  }
  const text = value.trim();
  if (text === '' || /e/i.test(text)) {
    return undefined;
  }
  if (/^\d+$/.test(text)) {
    const number = Number(text);
    return number > 0 ? number : undefined;
  }
  if (!/^\d+\.\d+$/.test(text)) {
    return undefined;
  }
  const number = Number(text);
  if (!Number.isInteger(number) || number <= 0) {
    return undefined;
  }
  return number;
}

/** Blockers still true for this draft and the rows selected with it. */
export function visibleBlockers(
  row: EnrichmentProposal,
  override: EnrichmentOverride,
  context: BlockerContext
): EnrichmentBlocker[] {
  const notes: EnrichmentBlocker[] = [];
  if (row.status === 'pending' && (row.kind === 'create_pricing' || row.kind === 'create_schedule')) {
    const activity = activityBlocker(row, override, context);
    const venue = venueBlocker(row, override, context);
    if (activity) {
      notes.push(activity);
    }
    if (venue) {
      notes.push(venue);
    }
  }
  const proposed = row.proposed_value;
  const type = override.pricing_type || String(proposed.pricing_type ?? '');
  for (const item of row.blockers ?? []) {
    if (item.field === 'activity_name' || item.field === 'location_id') {
      continue;
    }
    if (item.field === 'sessions_count') {
      if (type !== 'per_sessions') {
        continue;
      }
      const raw =
        override.sessions_count !== undefined
          ? override.sessions_count
          : proposed.sessions_count;
      if (positiveSessions(raw) !== undefined) {
        continue;
      }
    } else if (item.field === 'pricing_type') {
      if (override.pricing_type && pricingTypes.has(override.pricing_type)) {
        continue;
      }
    } else if (item.field === 'amount') {
      if (override.amount !== undefined && validAmount(override.amount)) {
        continue;
      }
    } else if (item.field === 'currency') {
      if (override.currency && /^[A-Za-z]{3}$/.test(override.currency)) {
        continue;
      }
    }
    notes.push(item);
  }
  return notes;
}

export function firstBlockerMessage(
  selected: string[],
  proposals: EnrichmentProposal[],
  overrides: Record<string, EnrichmentOverride>,
  venues?: EnrichmentRead['venues'],
  activities?: EnrichmentRead['activities']
): string {
  const context = { proposals, selected, venues, activities };
  for (const id of selected) {
    const row = proposals.find((item) => item.id === id);
    if (!row) {
      continue;
    }
    const note = visibleBlockers(row, overrides[id] ?? {}, context)[0];
    if (note) {
      return note.message;
    }
  }
  return '';
}

/** Override keys that differ from the stored proposal. */
export function chosenEnrichmentOverrides(
  selected: string[],
  overrides: Record<string, EnrichmentOverride>,
  proposals: EnrichmentProposal[]
): Record<string, EnrichmentOverride> {
  const body: Record<string, EnrichmentOverride> = {};
  for (const id of selected) {
    const draft = overrides[id];
    if (!draft) {
      continue;
    }
    const proposed = proposals.find((item) => item.id === id)?.proposed_value ?? {};
    const cleaned: EnrichmentOverride = {};
    if (draft.area_id) {
      cleaned.area_id = draft.area_id;
    }
    if (draft.category_id) {
      cleaned.category_id = draft.category_id;
    }
    if (draft.activity_id) {
      cleaned.activity_id = draft.activity_id;
    }
    if (draft.location_id) {
      cleaned.location_id = draft.location_id;
    }
    if (draft.age_min !== undefined && !Number.isNaN(draft.age_min)) {
      cleaned.age_min = draft.age_min;
    }
    if (draft.age_max !== undefined && !Number.isNaN(draft.age_max)) {
      cleaned.age_max = draft.age_max;
    }
    if (
      draft.pricing_type &&
      pricingTypes.has(draft.pricing_type) &&
      draft.pricing_type !== String(proposed.pricing_type ?? '')
    ) {
      cleaned.pricing_type = draft.pricing_type;
    }
    if (
      draft.amount !== undefined &&
      draft.amount !== '' &&
      draft.amount !== String(proposed.amount ?? '')
    ) {
      cleaned.amount = draft.amount;
    }
    const proposedCurrency = String(proposed.currency || 'HKD');
    if (draft.currency && draft.currency !== proposedCurrency) {
      cleaned.currency = draft.currency;
    }
    const type = draft.pricing_type ?? String(proposed.pricing_type ?? '');
    const count = positiveSessions(draft.sessions_count);
    if (
      type === 'per_sessions' &&
      count !== undefined &&
      count !== positiveSessions(proposed.sessions_count)
    ) {
      cleaned.sessions_count = count;
    }
    if (Object.keys(cleaned).length > 0) {
      body[id] = cleaned;
    }
  }
  return body;
}

function activityBlocker(
  row: EnrichmentProposal,
  override: EnrichmentOverride,
  context: BlockerContext
): EnrichmentBlocker | null {
  if (override.activity_id || siblingActivityMatches(row, context)) {
    return null;
  }
  if (context.activities) {
    if (knownName(row.proposed_value.activity_name, context.activities.map((item) => item.name))) {
      return null;
    }
    return {
      field: 'activity_name',
      message: row.kind === 'create_pricing' ? PRICE_ACTIVITY : SCHEDULE_ACTIVITY,
    };
  }
  return row.blockers?.find((item) => item.field === 'activity_name') ?? null;
}

function venueBlocker(
  row: EnrichmentProposal,
  override: EnrichmentOverride,
  context: BlockerContext
): EnrichmentBlocker | null {
  if (override.location_id) {
    return null;
  }
  if (context.venues) {
    if (knownVenue(row.proposed_value, venueAddresses(row, context))) {
      return null;
    }
    return {
      field: 'location_id',
      message: row.kind === 'create_pricing' ? PRICE_VENUE : SCHEDULE_VENUE,
    };
  }
  return row.blockers?.find((item) => item.field === 'location_id') ?? null;
}

function siblingActivityMatches(row: EnrichmentProposal, context: BlockerContext): boolean {
  const target = fold(row.proposed_value.activity_name);
  if (!target) {
    return false;
  }
  return selectedPending(context).some(
    (item) => item.kind === 'create_activity' && fold(item.proposed_value.name) === target
  );
}

function venueAddresses(row: EnrichmentProposal, context: BlockerContext): string[] {
  const addresses = (context.venues ?? []).map((item) => String(item.address ?? ''));
  for (const item of selectedPending(context)) {
    if (item.id === row.id || item.kind !== 'create_location') {
      continue;
    }
    const address = String(item.proposed_value.address ?? '').trim();
    if (address) {
      addresses.push(address);
    }
  }
  return addresses;
}

function selectedPending(context: BlockerContext): EnrichmentProposal[] {
  const chosen = new Set(context.selected);
  return context.proposals.filter((item) => chosen.has(item.id) && item.status === 'pending');
}

function knownName(name: unknown, names: string[]): boolean {
  const target = fold(name);
  return target !== '' && names.some((item) => fold(item) === target);
}

function knownVenue(proposed: Record<string, unknown>, addresses: string[]): boolean {
  const address = fold(proposed.location_address);
  if (address && addresses.some((item) => fold(item) === address)) {
    return true;
  }
  return addresses.length === 1;
}

function fold(value: unknown): string {
  return String(value ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase();
}

function validAmount(value: string): boolean {
  const amount = Number(value);
  return value.trim() !== '' && Number.isFinite(amount) && amount >= 0;
}
