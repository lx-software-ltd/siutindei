import { statSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { homeWizardChoices } from '@/lib/home-wizard/choices';
import {
  configuredHeroScopeSigns,
  heroScopeSignsFor,
} from '@/lib/home-wizard/area-scope';

const PUBLIC_DIR = resolve(__dirname, '../../public');

describe('heroScopeSignsFor', () => {
  it('returns nothing when the scope is blank, unknown, or all of Hong Kong', () => {
    expect(heroScopeSignsFor(undefined)).toEqual([]);
    expect(heroScopeSignsFor(' , ')).toEqual([]);
    expect(heroScopeSignsFor('atlantis')).toEqual([]);
    expect(
      heroScopeSignsFor(
        'hong_kong_island,kowloon,new_territories,islands',
      ),
    ).toEqual([]);
  });

  it('keeps one plate per token, in the written order, and stops at three', () => {
    expect(heroScopeSignsFor(' southern-stanley ')).toEqual([
      { id: 'southern-stanley', en: 'Stanley', zhHK: '赤柱' },
    ]);
    expect(
      heroScopeSignsFor('southern-repulse-bay, southern-stanley').map(
        (sign) => sign.id,
      ),
    ).toEqual(['southern-repulse-bay', 'southern-stanley']);
    expect(
      heroScopeSignsFor('southern-stanley, atlantis, southern-stanley').map(
        (sign) => sign.id,
      ),
    ).toEqual(['southern-stanley']);
    expect(heroScopeSignsFor('southern').map((sign) => sign.id)).toEqual([
      'southern-pok-fu-lam',
      'southern-aberdeen',
      'southern-ap-lei-chau',
    ]);
    expect(heroScopeSignsFor('kowloon, southern-stanley')).toEqual([
      { id: 'kowloon', en: 'Kowloon', zhHK: '九龍' },
      { id: 'southern-stanley', en: 'Stanley', zhHK: '赤柱' },
    ]);
    expect(heroScopeSignsFor('islands')).toEqual([
      { id: 'islands', en: 'Islands', zhHK: '離島' },
    ]);
  });

  it('reads the configured variable', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-shek-o';
    expect(configuredHeroScopeSigns().map((sign) => sign.en)).toEqual([
      'Shek O',
    ]);
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    expect(configuredHeroScopeSigns()).toEqual([]);
  });

  it('has a plate picture for every region and neighbourhood', () => {
    const ids = [
      ...homeWizardChoices.regions.map((region) => region.id),
      ...homeWizardChoices.neighbourhoods.map((place) => place.id),
    ];
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      const file = resolve(PUBLIC_DIR, `images/scope-signs/${id}.webp`);
      expect(statSync(file).size, id).toBeGreaterThan(500);
    }
  });
});
