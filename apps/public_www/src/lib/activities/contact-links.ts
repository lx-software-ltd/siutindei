import type { OrganizationContact } from './types';

export type ContactLinkKind =
  | 'website'
  | 'phone'
  | 'email'
  | 'whatsapp'
  | 'facebook'
  | 'instagram'
  | 'tiktok'
  | 'twitter'
  | 'xiaohongshu'
  | 'wechat';

export interface ContactLink {
  readonly kind: ContactLinkKind;
  /** Null for WeChat, which has no public profile URL. */
  readonly href: string | null;
  readonly text: string;
}

/** Calling codes for the countries the admin console offers most often. */
const CALLING_CODES: Record<string, string> = {
  HK: '852',
  MO: '853',
  CN: '86',
  TW: '886',
  SG: '65',
  MY: '60',
  JP: '81',
  KR: '82',
  GB: '44',
  US: '1',
  CA: '1',
  AU: '61',
  AE: '971',
};

const SOCIAL_PROFILE_BASE: Record<
  'facebook' | 'instagram' | 'tiktok' | 'twitter' | 'xiaohongshu',
  string
> = {
  facebook: 'https://www.facebook.com/',
  instagram: 'https://www.instagram.com/',
  tiktok: 'https://www.tiktok.com/@',
  twitter: 'https://x.com/',
  xiaohongshu: 'https://www.xiaohongshu.com/user/profile/',
};

function looksLikeUrl(value: string): boolean {
  const lower = value.toLowerCase();
  return (
    lower.startsWith('http://') ||
    lower.startsWith('https://') ||
    lower.startsWith('www.') ||
    value.includes('/')
  );
}

/** An http(s) URL, or null for anything else (javascript:, mailto:, ...). */
export function safeWebUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const parsed = new URL(withScheme);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
      return null;
    }
    if (!parsed.hostname.includes('.')) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

function displayHost(url: string): string {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname === '/' ? '' : parsed.pathname.replace(/\/$/, '');
    return `${parsed.hostname.replace(/^www\./, '')}${path}`;
  } catch {
    return url;
  }
}

function stripHandle(value: string): string {
  return value.trim().replace(/^@+/, '');
}

export function socialProfileUrl(
  kind: keyof typeof SOCIAL_PROFILE_BASE,
  value: string,
): string | null {
  if (looksLikeUrl(value)) {
    return safeWebUrl(value);
  }
  const handle = stripHandle(value);
  if (!/^[\w.-]+$/.test(handle)) {
    return null;
  }
  return `${SOCIAL_PROFILE_BASE[kind]}${encodeURIComponent(handle)}`;
}

function digitsOnly(value: string): string {
  return value.replace(/\D/g, '');
}

/** "+852 9123 4567" for display, or the national digits when the code is unknown. */
export function formatPhone(
  countryCode: string | null,
  nationalNumber: string,
): { readonly display: string; readonly e164: string | null } {
  const digits = digitsOnly(nationalNumber);
  const callingCode = countryCode ? CALLING_CODES[countryCode.toUpperCase()] : undefined;
  const grouped =
    digits.length === 8 ? `${digits.slice(0, 4)} ${digits.slice(4)}` : digits;
  if (!callingCode) {
    return { display: grouped, e164: null };
  }
  return { display: `+${callingCode} ${grouped}`, e164: `+${callingCode}${digits}` };
}

function whatsappUrl(
  value: string,
  countryCode: string | null,
): string | null {
  if (looksLikeUrl(value)) {
    return safeWebUrl(value);
  }
  let digits = digitsOnly(value);
  if (!digits) {
    return null;
  }
  const callingCode = countryCode ? CALLING_CODES[countryCode.toUpperCase()] : undefined;
  if (!value.trim().startsWith('+') && digits.length === 8 && callingCode) {
    digits = `${callingCode}${digits}`;
  }
  return `https://wa.me/${digits}`;
}

/** Every contact the organiser published, as display text and a safe href. */
export function contactLinks(contact: OrganizationContact | null | undefined): readonly ContactLink[] {
  if (!contact) {
    return [];
  }
  const links: ContactLink[] = [];
  if (contact.website) {
    const href = safeWebUrl(contact.website);
    if (href) {
      links.push({ kind: 'website', href, text: displayHost(href) });
    }
  }
  if (contact.phoneNumber) {
    const phone = formatPhone(contact.phoneCountryCode, contact.phoneNumber);
    links.push({
      kind: 'phone',
      href: `tel:${phone.e164 ?? digitsOnly(contact.phoneNumber)}`,
      text: phone.display,
    });
  }
  if (contact.email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email)) {
    links.push({ kind: 'email', href: `mailto:${contact.email}`, text: contact.email });
  }
  if (contact.whatsapp) {
    const href = whatsappUrl(contact.whatsapp, contact.phoneCountryCode);
    if (href) {
      links.push({ kind: 'whatsapp', href, text: 'WhatsApp' });
    }
  }
  for (const kind of ['instagram', 'facebook', 'tiktok', 'twitter', 'xiaohongshu'] as const) {
    const value = contact[kind];
    if (!value) {
      continue;
    }
    const href = socialProfileUrl(kind, value);
    if (href) {
      links.push({
        kind,
        href,
        text: looksLikeUrl(value) ? displayHost(href) : `@${stripHandle(value)}`,
      });
    }
  }
  if (contact.wechat) {
    links.push({ kind: 'wechat', href: null, text: stripHandle(contact.wechat) });
  }
  return links;
}
