import { DEFAULT_LOCALE, isValidLocale, type Locale } from '@/content/locales';
import { getHrefKind, isExternalHref } from '@/lib/url-utils';

function sanitizePath(path: string): string {
  let value = path.trim();

  if (value === '' || value === '#') {
    return value || '/';
  }

  if (/^https?:\/\//i.test(value)) {
    try {
      value = new URL(value).pathname;
    } catch {
      return value;
    }
  }

  value = value.split('#')[0] ?? value;
  value = value.split('?')[0] ?? value;

  if (!value.startsWith('/')) {
    value = `/${value}`;
  }

  return value.replace(/\/+$/, '') || '/';
}

export function getLocaleFromPath(path: string): Locale {
  const segments = sanitizePath(path).split('/').filter(Boolean);
  if (segments.length > 0 && isValidLocale(segments[0])) {
    return segments[0];
  }

  return DEFAULT_LOCALE;
}

export function normalizeLocalizedPath(path: string): string {
  let value = sanitizePath(path);
  const segments = value.split('/').filter(Boolean);

  if (segments.length > 0 && isValidLocale(segments[0])) {
    const localizedValue = `/${segments.slice(1).join('/')}`;
    value = localizedValue === '/' ? '/' : localizedValue;
  }

  return value || '/';
}

export function localizePath(path: string, locale: Locale): string {
  const basePath = normalizeLocalizedPath(path);
  return basePath === '/' ? `/${locale}/` : `/${locale}${basePath}/`;
}

export function localizeHref(href: string, locale: Locale): string {
  const value = href.trim();
  if (value === '' || value === '#') {
    return value || '/';
  }

  if (getHrefKind(value) === 'unsafe') {
    return value;
  }

  if (isExternalHref(value)) {
    return value;
  }

  const hashIndex = value.indexOf('#');
  const hashValue = hashIndex >= 0 ? value.slice(hashIndex) : '';
  const withoutHash = hashIndex >= 0 ? value.slice(0, hashIndex) : value;
  const queryIndex = withoutHash.indexOf('?');
  const queryValue = queryIndex >= 0 ? withoutHash.slice(queryIndex) : '';
  const pathnameValue =
    queryIndex >= 0 ? withoutHash.slice(0, queryIndex) : withoutHash;

  return `${localizePath(pathnameValue || '/', locale)}${queryValue}${hashValue}`;
}
