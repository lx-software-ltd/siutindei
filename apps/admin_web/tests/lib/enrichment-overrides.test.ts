import { describe, expect, it } from 'vitest';

import type { EnrichmentProposal } from '@/lib/api-client-enrichment';
import {
  chosenEnrichmentOverrides,
  firstBlockerMessage,
  visibleBlockers,
} from '@/lib/enrichment-overrides';

const price: EnrichmentProposal = {
  id: 'price-1',
  section: 'Pricing',
  kind: 'create_pricing',
  field: null,
  label: 'Price',
  current_value: null,
  proposed_value: {
    pricing_type: 'per_sessions',
    amount: '500',
    currency: 'USD',
  },
  confidence: 0.5,
  unverified: true,
  evidence: [],
  status: 'pending',
  blockers: [
    {
      field: 'sessions_count',
      message: 'Add the number of classes for this term price',
    },
  ],
};

describe('enrichment pricing overrides', () => {
  it('sends only the price fields the reviewer changed', () => {
    expect(
      chosenEnrichmentOverrides(
        ['price-1'],
        {
          'price-1': {
            sessions_count: 8,
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

  it('hides the term-length note once the reviewer fills it', () => {
    expect(firstBlockerMessage(['price-1'], [price], {})).toBe(
      'Add the number of classes for this term price'
    );
    expect(
      visibleBlockers(
        price.blockers,
        { sessions_count: 8 },
        price.proposed_value
      )
    ).toEqual([]);
  });
});
