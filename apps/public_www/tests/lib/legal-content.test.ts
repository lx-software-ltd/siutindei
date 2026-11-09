import { describe, expect, it } from 'vitest';

import { getLegalContent } from '@/lib/legal-copy';

const enContent = { legal: getLegalContent('en') };
const zhHKContent = { legal: getLegalContent('zh-HK') };

const CONTACT_EMAIL = 'support@siutindei.com';

describe('legal content', () => {
  const documents = ['privacy', 'terms'] as const;

  it.each(documents)(
    'keeps %s section ids aligned across locales',
    (documentKey) => {
      const enSections = enContent.legal[documentKey].sections;
      const zhSections = zhHKContent.legal[documentKey].sections;

      expect(zhSections.map((section) => section.id)).toEqual(
        enSections.map((section) => section.id),
      );
    },
  );

  it.each(documents)('gives every %s section unique ids', (documentKey) => {
    const ids = enContent.legal[documentKey].sections.map(
      (section) => section.id,
    );
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('anchors the PICS and cookies sections in the privacy policy', () => {
    const ids = enContent.legal.privacy.sections.map((section) => section.id);
    expect(ids).toContain('pics');
    expect(ids).toContain('cookies');
  });

  it.each(documents)(
    'includes the data request contact email in %s for both locales',
    (documentKey) => {
      for (const content of [enContent, zhHKContent]) {
        const serialized = JSON.stringify(content.legal[documentKey]);
        expect(serialized).toContain(CONTACT_EMAIL);
      }
    },
  );

  it('dates the contact-address revision in both locales', () => {
    expect(enContent.legal.lastUpdated).toBe('9 November 2026');
    expect(zhHKContent.legal.lastUpdated).toBe('2026年11月9日');
  });

  it('names LX Software as a Hong Kong sole proprietorship', () => {
    const enSerialized = JSON.stringify(enContent.legal);
    const zhSerialized = JSON.stringify(zhHKContent.legal);
    expect(enSerialized).not.toContain('LX Software Limited');
    expect(zhSerialized).not.toContain('LX Software Limited');
    expect(enSerialized).toContain(
      'LX Software (a sole proprietorship registered in Hong Kong)',
    );
    expect(zhSerialized).toContain('於香港註冊的獨資企業');
  });
});
