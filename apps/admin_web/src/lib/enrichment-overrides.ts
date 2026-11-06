import type {
  EnrichmentBlocker,
  EnrichmentOverride,
  EnrichmentProposal,
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

function wholeNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isInteger(value)) {
    return value;
  }
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    return Number(value);
  }
  return undefined;
}

/** Blockers the reviewer has not already answered in this draft. */
export function visibleBlockers(
  blockers: EnrichmentBlocker[] | undefined,
  override: EnrichmentOverride,
  proposed: Record<string, unknown>
): EnrichmentBlocker[] {
  const type = override.pricing_type || String(proposed.pricing_type ?? '');
  return (blockers ?? []).filter((item) => {
    if (item.field === 'sessions_count') {
      if (type !== 'per_sessions') {
        return false;
      }
      const count = override.sessions_count ?? wholeNumber(proposed.sessions_count);
      return !(typeof count === 'number' && count > 0);
    }
    if (item.field === 'location_id') {
      return !override.location_id;
    }
    if (item.field === 'pricing_type') {
      return !(override.pricing_type && pricingTypes.has(override.pricing_type));
    }
    if (item.field === 'amount') {
      if (override.amount === undefined) {
        return true;
      }
      const amount = Number(override.amount);
      return !(
        override.amount.trim() !== '' &&
        Number.isFinite(amount) &&
        amount >= 0
      );
    }
    if (item.field === 'currency') {
      return !(override.currency && /^[A-Za-z]{3}$/.test(override.currency));
    }
    return true;
  });
}

export function firstBlockerMessage(
  selected: string[],
  proposals: EnrichmentProposal[],
  overrides: Record<string, EnrichmentOverride>
): string {
  for (const id of selected) {
    const row = proposals.find((item) => item.id === id);
    if (!row) {
      continue;
    }
    const note = visibleBlockers(
      row.blockers,
      overrides[id] ?? {},
      row.proposed_value
    )[0];
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
    const proposed =
      proposals.find((item) => item.id === id)?.proposed_value ?? {};
    const cleaned: EnrichmentOverride = {};
    if (draft.area_id) {
      cleaned.area_id = draft.area_id;
    }
    if (draft.category_id) {
      cleaned.category_id = draft.category_id;
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
    const proposedSessions = wholeNumber(proposed.sessions_count);
    if (
      type === 'per_sessions' &&
      draft.sessions_count !== undefined &&
      !Number.isNaN(draft.sessions_count) &&
      draft.sessions_count !== proposedSessions
    ) {
      cleaned.sessions_count = draft.sessions_count;
    }
    if (Object.keys(cleaned).length > 0) {
      body[id] = cleaned;
    }
  }
  return body;
}
