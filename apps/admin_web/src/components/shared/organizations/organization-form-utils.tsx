'use client';

import type { ReactNode } from 'react';

import {
  parsePhoneNumberFromString,
  type CountryCode,
} from 'libphonenumber-js';

import {
  emptyTranslations,
  extractTranslations,
  type TranslationLanguageCode,
} from '../../../lib/translations';
import type { CognitoUser, Organization } from '../../../types/admin';

interface IconProps {
  className?: string;
}

export function PhoneIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden='true'
    >
      <path d='M22 16.9v3a2 2 0 0 1-2.2 2' />
      <path d='M3 5a2 2 0 0 1 2-2h3' />
      <path d='M5 3h3a2 2 0 0 1 2 1.7' />
      <path d='M8.6 7.6a16 16 0 0 0 7.8 7.8' />
      <path d='M16.4 15.4 20 14a2 2 0 0 1 2 1.3' />
    </svg>
  );
}

export function EmailIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden='true'
    >
      <rect x='2' y='4' width='20' height='16' rx='2' />
      <path d='m22 7-10 6L2 7' />
    </svg>
  );
}

export function ServiceIcon({ className, src }: IconProps & { src: string }) {
  return (
    <img
      className={className}
      src={src}
      alt=''
      aria-hidden='true'
      loading='lazy'
      width={16}
      height={16}
    />
  );
}

export function ContactIcon({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <span className='inline-flex items-center' title={label} aria-label={label}>
      {children}
    </span>
  );
}

export interface OrganizationFormState {
  name: string;
  description: string;
  name_translations: Record<TranslationLanguageCode, string>;
  description_translations: Record<TranslationLanguageCode, string>;
  manager_id: string;
  phone_country_code: string;
  phone_number: string;
  email: string;
  whatsapp: string;
  facebook: string;
  instagram: string;
  tiktok: string;
  twitter: string;
  xiaohongshu: string;
  wechat: string;
  status: string;
}

export const emptyForm: OrganizationFormState = {
  name: '',
  description: '',
  name_translations: emptyTranslations(),
  description_translations: emptyTranslations(),
  manager_id: '',
  phone_country_code: 'HK',
  phone_number: '',
  email: '',
  whatsapp: '',
  facebook: '',
  instagram: '',
  tiktok: '',
  twitter: '',
  xiaohongshu: '',
  wechat: '',
  status: 'operational',
};

export function itemToForm(item: Organization): OrganizationFormState {
  return {
    name: item.name ?? '',
    description: item.description ?? '',
    name_translations: extractTranslations(item.name_translations),
    description_translations: extractTranslations(item.description_translations),
    manager_id: item.manager_id ?? '',
    phone_country_code: item.phone_country_code ?? 'HK',
    phone_number: item.phone_number ?? '',
    email: item.email ?? '',
    whatsapp: item.whatsapp ?? '',
    facebook: item.facebook ?? '',
    instagram: item.instagram ?? '',
    tiktok: item.tiktok ?? '',
    twitter: item.twitter ?? '',
    xiaohongshu: item.xiaohongshu ?? '',
    wechat: item.wechat ?? '',
    status: item.status ?? 'operational',
  };
}

export type SocialFieldKey =
  | 'whatsapp'
  | 'facebook'
  | 'instagram'
  | 'tiktok'
  | 'twitter'
  | 'xiaohongshu'
  | 'wechat';

const SOCIAL_ICON_BASE_URL = 'https://api.iconify.design/simple-icons';

function buildSocialIconUrl(slug: string, color: string): string {
  return `${SOCIAL_ICON_BASE_URL}/${slug}.svg?color=%23${color}`;
}

export const SOCIAL_FIELDS: Array<{
  key: SocialFieldKey;
  label: string;
  iconSrc: string;
}> = [
  {
    key: 'whatsapp',
    label: 'WhatsApp',
    iconSrc: buildSocialIconUrl('whatsapp', '25D366'),
  },
  {
    key: 'facebook',
    label: 'Facebook',
    iconSrc: buildSocialIconUrl('facebook', '1877F2'),
  },
  {
    key: 'instagram',
    label: 'Instagram',
    iconSrc: buildSocialIconUrl('instagram', 'E4405F'),
  },
  {
    key: 'tiktok',
    label: 'TikTok',
    iconSrc: buildSocialIconUrl('tiktok', '000000'),
  },
  {
    key: 'twitter',
    label: 'X',
    iconSrc: buildSocialIconUrl('x', '000000'),
  },
  {
    key: 'xiaohongshu',
    label: 'Xiaohongshu',
    iconSrc: buildSocialIconUrl('xiaohongshu', 'FF2442'),
  },
  {
    key: 'wechat',
    label: 'WeChat',
    iconSrc: buildSocialIconUrl('wechat', '07C160'),
  },
];

export function hasValue(value?: string | null): boolean {
  return Boolean(value && value.trim().length > 0);
}

export function isValidEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
}

function looksLikeUrl(value: string): boolean {
  const lower = value.toLowerCase();
  if (lower.startsWith('http://') || lower.startsWith('https://')) {
    return true;
  }
  if (lower.startsWith('www.')) {
    return true;
  }
  return value.includes('/');
}

function normalizeSocialUrl(value: string): string {
  const trimmed = value.trim();
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

function isValidUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function isValidSocialHandle(value: string): boolean {
  return /^@?[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(value);
}

export function normalizeSocialValue(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  if (looksLikeUrl(trimmed)) {
    return normalizeSocialUrl(trimmed);
  }
  return trimmed;
}

export function normalizePhoneNumber(value: string): string {
  return value.replace(/\D/g, '');
}

export function isValidPhoneNumber(
  countryCode: string,
  number: string
): boolean {
  if (!countryCode) {
    return false;
  }
  try {
    const parsed = parsePhoneNumberFromString(number, countryCode as CountryCode);
    return Boolean(parsed && parsed.isValid());
  } catch {
    return false;
  }
}

export function getManagerDisplayName(
  managerId: string,
  users: CognitoUser[]
): string {
  const user = users.find((u) => u.sub === managerId);
  if (!user) {
    return managerId.slice(0, 8) + '...';
  }
  return user.email || user.username || user.sub.slice(0, 8) + '...';
}

export function isValidSocialValue(value: string): boolean {
  if (!value) {
    return true;
  }
  if (looksLikeUrl(value)) {
    return isValidUrl(normalizeSocialUrl(value));
  }
  return isValidSocialHandle(value);
}
