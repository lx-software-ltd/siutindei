import { describe, expect, it } from 'vitest';

import { contactLinks, formatPhone, safeWebUrl } from '@/lib/activities/contact-links';
import type { OrganizationContact } from '@/lib/activities/types';

const EMPTY: OrganizationContact = {
  website: null,
  email: null,
  phoneCountryCode: null,
  phoneNumber: null,
  whatsapp: null,
  facebook: null,
  instagram: null,
  tiktok: null,
  twitter: null,
  xiaohongshu: null,
  wechat: null,
};

describe('contactLinks', () => {
  it('turns handles into profile links and keeps URLs', () => {
    const links = contactLinks({
      ...EMPTY,
      website: 'studio.example',
      instagram: '@studio_example',
      facebook: 'https://facebook.com/studio.example',
      wechat: 'studio-wechat',
    });
    expect(links.map((link) => [link.kind, link.href, link.text])).toEqual([
      ['website', 'https://studio.example/', 'studio.example'],
      ['instagram', 'https://www.instagram.com/studio_example', '@studio_example'],
      ['facebook', 'https://facebook.com/studio.example', 'facebook.com/studio.example'],
      ['wechat', null, 'studio-wechat'],
    ]);
  });

  it('formats a Hong Kong phone and WhatsApp number', () => {
    const links = contactLinks({
      ...EMPTY,
      phoneCountryCode: 'HK',
      phoneNumber: '91234567',
      whatsapp: '91234567',
    });
    expect(links).toEqual([
      { kind: 'phone', href: 'tel:+85291234567', text: '+852 9123 4567' },
      { kind: 'whatsapp', href: 'https://wa.me/85291234567', text: 'WhatsApp' },
    ]);
  });

  it('drops unsafe or malformed values', () => {
    expect(safeWebUrl('javascript:alert(1)')).toBeNull();
    expect(
      contactLinks({ ...EMPTY, website: 'javascript:alert(1)', email: 'not-an-email' }),
    ).toEqual([]);
    expect(contactLinks(null)).toEqual([]);
  });

  it('keeps national digits when the country is unknown', () => {
    expect(formatPhone(null, '2345 6789')).toEqual({ display: '2345 6789', e164: null });
  });
});
