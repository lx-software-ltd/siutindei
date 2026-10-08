'use client';

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
  source: string;
  source_id: string;
  source_url: string;
  source_note: string;
  description_source: string;
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
  source: '',
  source_id: '',
  source_url: '',
  source_note: '',
  description_source: '',
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
    source: item.source ?? '',
    source_id: item.source_id ?? '',
    source_url: item.source_url ?? '',
    source_note: item.source_note ?? '',
    description_source: item.description_source ?? '',
  };
}

export const ORG_SOURCE_OPTIONS = [
  { value: 'lcsd', label: 'LCSD' },
  { value: 'edb', label: 'EDB' },
  { value: 'swd', label: 'SWD' },
  { value: 'places', label: 'Places' },
  { value: 'competitor', label: 'Competitor' },
] as const;

export const DESCRIPTION_SOURCE_OPTIONS = [
  { value: 'template', label: 'Template' },
  { value: 'official', label: 'Official' },
  { value: 'places', label: 'Places' },
  { value: 'enrich', label: 'Enriched' },
] as const;

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
