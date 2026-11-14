import { describe, expect, it } from 'vitest';

import {
  activityFormFromSnapshot,
  organizationFormFromSnapshot,
  snapshotFieldText,
  type ActivitySnapshotForm,
} from '@/components/admin/catalog-version-snapshot';
import {
  checkedDateInput,
  checkedDatePayload,
  emptyForm,
  todayCheckedDate,
} from '@/components/shared/organizations/organization-form-utils';
import {
  FACT_KEYS,
  LISTING_KIND_OPTIONS,
  categoryKindRule,
  factsForKind,
  kindForCategoryRule,
  factsSummary,
  isListingKind,
  listingKindLabel,
  setFact,
} from '@/lib/listing-kinds';

describe('listing kinds', () => {
  it('offers every kind with fact keys', () => {
    expect(LISTING_KIND_OPTIONS.map((option) => option.value)).toEqual([
      'class',
      'camp',
      'place',
      'preschool',
      'eat',
    ]);
    for (const option of LISTING_KIND_OPTIONS) {
      expect(FACT_KEYS[option.value]).toBeDefined();
    }
    expect(FACT_KEYS.preschool).toEqual([]);
  });

  it('recognises kinds and labels them', () => {
    expect(isListingKind('place')).toBe(true);
    expect(isListingKind('museum')).toBe(false);
    expect(isListingKind(null)).toBe(false);
    expect(listingKindLabel('eat')).toBe('Eat with kids');
    expect(listingKindLabel('museum')).toBeNull();
  });

  it('keeps only boolean facts the kind allows', () => {
    expect(
      factsForKind('place', {
        toilets: true,
        shade: false,
        drop_in: true,
        fenced: 'yes',
      })
    ).toEqual({ toilets: true, shade: false });
    expect(factsForKind('class', null)).toEqual({});
    expect(factsForKind('class', ['drop_in'])).toEqual({});
  });

  it('sets and clears a fact without mutating the input', () => {
    const facts = { toilets: true };
    expect(setFact(facts, 'shade', false)).toEqual({
      toilets: true,
      shade: false,
    });
    expect(setFact(facts, 'toilets', undefined)).toEqual({});
    expect(facts).toEqual({ toilets: true });
  });

  it('summarises facts for version history', () => {
    expect(factsSummary({ toilets: true, shade: false })).toBe(
      'Toilets: yes, Shade: no'
    );
    expect(factsSummary({})).toBe('Not checked');
    expect(factsSummary(undefined)).toBe('Not checked');
  });
});

describe('checked dates', () => {
  it('reads a timestamp as a Hong Kong date', () => {
    expect(checkedDateInput('2026-03-01T18:30:00Z')).toBe('2026-03-02');
    expect(checkedDateInput('2026-03-01T00:00:00+08:00')).toBe('2026-03-01');
    expect(checkedDateInput(null)).toBe('');
    expect(checkedDateInput('not a date')).toBe('');
  });

  it('uses the Hong Kong day for today', () => {
    expect(todayCheckedDate(new Date('2026-03-01T17:00:00Z'))).toBe(
      '2026-03-02'
    );
  });

  it('sends a picked date as Hong Kong midnight', () => {
    const payload = checkedDatePayload('2026-03-02');
    expect(payload).toBe('2026-03-02T00:00:00+08:00');
    expect(checkedDateInput(payload)).toBe('2026-03-02');
  });
});

describe('version snapshots', () => {
  const activityFallback: ActivitySnapshotForm = {
    name: 'Live',
    description: '',
    name_translations: { zh: '', yue: '' },
    description_translations: { zh: '', yue: '' },
    age_min: '',
    age_max: '',
    source_url: '',
    source_note: '',
    category_id: '',
    org_id: '',
    kind: 'place',
    facts: { toilets: true },
  };

  it('reads kind and facts from an activity snapshot', () => {
    const next = activityFormFromSnapshot(
      { kind: 'eat', facts: { high_chairs: true, toilets: true } },
      activityFallback
    );
    expect(next.kind).toBe('eat');
    expect(next.facts).toEqual({ high_chairs: true });
  });

  it('reads an activity snapshot without kind as a class', () => {
    const next = activityFormFromSnapshot({ name: 'Old' }, activityFallback);
    expect(next.kind).toBe('class');
    expect(next.facts).toEqual({});
  });

  it('reads the checked date from an organization snapshot', () => {
    const fallback = {
      ...emptyForm,
      parent_verified: true,
      parent_verified_at: '2026-01-05',
    };
    const next = organizationFormFromSnapshot(
      {
        parent_verified: true,
        parent_verified_at: '2025-12-01T02:00:00+00:00',
      },
      fallback
    );
    expect(next.parent_verified_at).toBe('2025-12-01');

    const older = organizationFormFromSnapshot(
      { parent_verified: true },
      fallback
    );
    expect(older.parent_verified_at).toBe('');

    const partial = organizationFormFromSnapshot({ name: 'Merge' }, fallback);
    expect(partial.parent_verified_at).toBe('2026-01-05');
  });

  it('formats kind, facts, and checked date fields', () => {
    expect(snapshotFieldText('kind', 'camp')).toBe('Camps and workshops');
    expect(snapshotFieldText('kind', undefined)).toBe('Classes and clubs');
    expect(snapshotFieldText('facts', { drop_in: true })).toBe('Drop-in: yes');
    expect(
      snapshotFieldText('parent_verified_at', '2026-02-01T00:00:00+08:00')
    ).toBe('2026-02-01');
    expect(snapshotFieldText('parent_verified_at', null)).toBe('—');
  });
});

describe('kind from category', () => {
  it('follows a fixed root and limits a topic to classes and camps', () => {
    expect(categoryKindRule({ system_role: 'places' })).toEqual({ fixed: 'place' });
    expect(categoryKindRule({ system_role: 'nurseries' })).toEqual({
      fixed: 'preschool',
    });
    expect(categoryKindRule({ system_role: 'eat' })).toEqual({ fixed: 'eat' });
    expect(categoryKindRule({ system_role: 'schools' })).toBeNull();
    expect(categoryKindRule({ show_in_wizard: true })).toEqual({
      allowed: ['class', 'camp'],
    });
    expect(categoryKindRule({})).toBeNull();
    expect(categoryKindRule(undefined)).toBeNull();
  });

  it('keeps an allowed kind and replaces one the category does not take', () => {
    const topic = categoryKindRule({ show_in_wizard: true });
    expect(kindForCategoryRule(topic, 'camp')).toBe('camp');
    expect(kindForCategoryRule(topic, 'place')).toBe('class');
    expect(kindForCategoryRule({ fixed: 'place' }, 'camp')).toBe('place');
    expect(kindForCategoryRule(null, 'eat')).toBe('eat');
  });
});
