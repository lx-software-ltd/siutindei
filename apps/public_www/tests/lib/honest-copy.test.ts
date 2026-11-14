import { describe, expect, it } from 'vitest';

import en from '@/content/en.json';
import zh from '@/content/zh-HK.json';

const LOCALES = { en, 'zh-HK': zh } as const;

const FALSE_CLAIMS = [
  'checked by local parents before',
  'Checked by local parents.',
  '上架前都經本地家長審核',
];

const MONEY_WORDS = ['paid placement', 'sponsor', '贊助', '付費'];

const HONG_KONG_WIDE_KEYS = [
  ['hero', 'subtitle'],
  ['smallWorld', 'subtitle'],
  ['seo', 'fallbackDescription'],
  ['seo', 'search', 'description'],
  ['discovery', 'pageTitle'],
] as const;

function valueAt(content: unknown, path: readonly string[]): string {
  let node = content;
  for (const key of path) {
    node = (node as Record<string, unknown>)[key];
  }
  if (typeof node !== 'string') {
    throw new Error(`${path.join('.')} is not a string`);
  }
  return node;
}

describe('honest copy', () => {
  for (const [locale, content] of Object.entries(LOCALES)) {
    const raw = JSON.stringify(content);

    it(`does not claim every ${locale} listing is parent-checked`, () => {
      for (const claim of FALSE_CLAIMS) {
        expect(raw).not.toContain(claim);
      }
    });

    it(`says nothing about paying for a position in ${locale}`, () => {
      for (const word of MONEY_WORDS) {
        expect(raw.toLowerCase()).not.toContain(word.toLowerCase());
      }
    });

    it(`names the open area wherever ${locale} copy names Hong Kong`, () => {
      const stanley = locale === 'en' ? 'Stanley' : '赤柱';
      for (const path of HONG_KONG_WIDE_KEYS) {
        expect(valueAt(content, path)).toContain(stanley);
      }
    });
  }

  it('explains the badge and the free listing in both languages', () => {
    for (const content of Object.values(LOCALES)) {
      expect(content.activityDetail.parentVerifiedExplainer.length).toBeGreaterThan(0);
      const ids = content.pages.about.sections.map((section) => section.id);
      expect(ids).toEqual(expect.arrayContaining(['how-listings-are-checked', 'free']));
    }
    expect(zh.pages.about.sections.map((section) => section.id)).toEqual(
      en.pages.about.sections.map((section) => section.id),
    );
  });
});
