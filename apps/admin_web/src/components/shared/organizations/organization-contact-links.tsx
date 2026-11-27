import type { ReactNode } from 'react';

import {
  parsePhoneNumberFromString,
  type CountryCode,
} from 'libphonenumber-js/min';

import {
  isValidEmail,
  normalizePhoneNumber,
} from './organization-form-utils';

const HTTP_URL = /^https?:\/\//i;

/** `mailto:` for a valid address. Blank and invalid addresses have no link. */
export function organizationEmailHref(email: string): string | null {
  const trimmed = email.trim();
  if (!isValidEmail(trimmed)) {
    return null;
  }
  return `mailto:${trimmed}`;
}

/** http(s) URL for the website field. Other schemes are refused. */
export function organizationWebsiteHref(website: string): string | null {
  const trimmed = website.trim();
  if (!trimmed || trimmed.length > 400 || /[\s<>]/.test(trimmed)) {
    return null;
  }
  if (/^[a-z][a-z0-9+.-]*:/i.test(trimmed) && !HTTP_URL.test(trimmed)) {
    return null;
  }
  const candidate = HTTP_URL.test(trimmed) ? trimmed : `https://${trimmed}`;
  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }
    if (parsed.username || parsed.password) {
      return null;
    }
    if (!parsed.hostname.includes('.')) {
      return null;
    }
    return candidate;
  } catch {
    return null;
  }
}

/** `https://wa.me/` for a possible national number and its country code. */
export function organizationWhatsappHref(
  countryCode: string,
  phoneNumber: string
): string | null {
  const digits = normalizePhoneNumber(phoneNumber);
  const country = countryCode.trim().toUpperCase();
  if (!digits || !country) {
    return null;
  }
  let parsed;
  try {
    parsed = parsePhoneNumberFromString(digits, country as CountryCode);
  } catch {
    return null;
  }
  if (!parsed?.isPossible()) {
    return null;
  }
  const international = parsed.number.replace(/^\+/, '');
  if (!/^\d+$/.test(international)) {
    return null;
  }
  return `https://wa.me/${international}`;
}

/** Action under a contact field. Omitted when there is nothing safe to open. */
export function OrganizationContactLink({
  href,
  external = false,
  children,
}: {
  href: string | null;
  external?: boolean;
  children: ReactNode;
}) {
  if (!href) {
    return null;
  }
  return (
    <a
      href={href}
      className='admin-focus mt-1 inline-block text-sm text-ink-700 underline underline-offset-2 hover:text-ink-900'
      {...(external
        ? { target: '_blank', rel: 'noreferrer noopener' }
        : {})}
    >
      {children}
    </a>
  );
}
