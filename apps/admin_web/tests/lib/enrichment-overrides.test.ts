import { describe, expect, it } from 'vitest';

import type { EnrichmentProposal } from '@/lib/api-client-enrichment';
import {
  chosenEnrichmentOverrides,
  firstBlockerMessage,
  visibleBlockers,
} from '@/lib/enrichment-overrides';

const termNote = 'Add the number of classes for this term price';

const price: EnrichmentProposal = {
  id: 'price-1',
  section: 'Pricing',
  kind: 'create_pricing',
  field: null,
  label: 'Price',
  current_value: null,
  proposed_value: {
    activity_name: 'Painting',
    pricing_type: 'per_sessions',
    amount: '500',
    currency: 'USD',
    location_address: '',
  },
  confidence: 0.5,
  unverified: true,
  evidence: [],
  status: 'pending',
  blockers: [{ field: 'sessions_count', message: termNote }],
};

const context = {
  proposals: [price],
  selected: ['price-1'],
  venues: [{ id: 'venue-1', address: '1 Test Street' }],
  activities: [{ id: 'act-1', name: 'Painting' }],
};

describe('enrichment pricing overrides', () => {
  it('sends only the price fields the reviewer changed', () => {
    expect(
      chosenEnrichmentOverrides(
        ['price-1'],
        {
          'price-1': {
            sessions_count: '8',
            currency: 'HKD',
            amount: '500',
            pricing_type: 'per_sessions',
          },
        },
        [price]
      )
    ).toEqual({
      'price-1': { sessions_count: 8, currency: 'HKD' },
    });
  });

  it('keeps a partial class count on the row', () => {
    expect(firstBlockerMessage(['price-1'], [price], {}, context.venues, context.activities)).toBe(
      termNote
    );
    for (const typed of ['8.5', '8a', '1e1']) {
      expect(visibleBlockers(price, { sessions_count: typed }, context)[0]?.message).toBe(
        termNote
      );
      expect(
        chosenEnrichmentOverrides(
          ['price-1'],
          { 'price-1': { sessions_count: typed } },
          [price]
        )
      ).toEqual({});
    }
    expect(visibleBlockers(price, { sessions_count: '8' }, context)).toEqual([]);
  });

  it('hides the activity note only for a selected matching activity', () => {
    const activity: EnrichmentProposal = {
      ...price,
      id: 'act-new',
      section: 'Activities',
      kind: 'create_activity',
      proposed_value: { name: 'Painting' },
      blockers: [],
    };
    const unmatched = {
      ...price,
      blockers: [
        { field: 'activity_name', message: 'Pick the activity this price belongs to' },
      ],
    };
    const shared = {
      proposals: [unmatched, activity],
      venues: context.venues,
      activities: [] as { id: string; name: string }[],
    };
    expect(
      visibleBlockers(unmatched, {}, { ...shared, selected: ['price-1'] }).map(
        (item) => item.field
      )
    ).toContain('activity_name');
    expect(
      visibleBlockers(unmatched, {}, { ...shared, selected: ['price-1', 'act-new'] }).map(
        (item) => item.field
      )
    ).not.toContain('activity_name');
    expect(
      visibleBlockers(unmatched, { activity_id: 'act-1' }, {
        ...shared,
        selected: ['price-1'],
      })
    ).toEqual([]);
  });

  it('asks for a venue when the selection adds a second one', () => {
    const place: EnrichmentProposal = {
      ...price,
      id: 'place-1',
      section: 'Locations',
      kind: 'create_location',
      proposed_value: { address: '9 Other Road' },
      blockers: [],
    };
    const shared = {
      proposals: [price, place],
      venues: context.venues,
      activities: context.activities,
    };
    expect(
      visibleBlockers(price, { sessions_count: 8 }, { ...shared, selected: ['price-1'] })
    ).toEqual([]);
    expect(
      visibleBlockers(price, { sessions_count: 8 }, {
        ...shared,
        selected: ['price-1', 'place-1'],
      }).map((item) => item.field)
    ).toEqual(['location_id']);
  });
});
