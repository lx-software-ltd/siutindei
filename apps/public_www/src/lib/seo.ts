import type { Metadata } from 'next';

import { DEFAULT_LOCALE, SUPPORTED_LOCALES, type Locale } from '@/content/locales';
import {
  localizePath as localizeLocalizedPath,
  normalizeLocalizedPath,
} from '@/lib/locale-routing';

const SITE_ORIGIN_ENV_NAME = 'NEXT_PUBLIC_SITE_ORIGIN';
let cachedSiteOrigin: string | undefined;
let cachedSiteHost: string | undefined;

function normalizeSiteOrigin(rawOrigin: string): string {
  const normalizedOrigin = rawOrigin.trim();
  if (normalizedOrigin === '') {
    throw new Error(`${SITE_ORIGIN_ENV_NAME} must not be empty.`);
  }

  let parsedOrigin: URL;
  try {
    parsedOrigin = new URL(normalizedOrigin);
  } catch {
    throw new Error(`${SITE_ORIGIN_ENV_NAME} must be a valid absolute URL.`);
  }

  const protocol = parsedOrigin.protocol.toLowerCase();
  const hostname = parsedOrigin.hostname.toLowerCase();
  const isLocalhostHttpOrigin =
    protocol === 'http:' && hostname === 'localhost';
  if (protocol !== 'https:' && !isLocalhostHttpOrigin) {
    throw new Error(
      `${SITE_ORIGIN_ENV_NAME} must use https, or http://localhost for local development.`,
    );
  }

  if (
    parsedOrigin.pathname !== '/'
    || parsedOrigin.search !== ''
    || parsedOrigin.hash !== ''
  ) {
    throw new Error(
      `${SITE_ORIGIN_ENV_NAME} must not include a path, query string, or hash fragment.`,
    );
  }

  return parsedOrigin.origin;
}

function resolveSiteOrigin(): string {
  // Intentionally reads NEXT_PUBLIC_SITE_ORIGIN here (not site-config.ts) so
  // unit tests can fall back to globalThis.location.origin when unset.
  const configuredSiteOrigin = process.env.NEXT_PUBLIC_SITE_ORIGIN?.trim() ?? '';
  if (configuredSiteOrigin !== '') {
    return normalizeSiteOrigin(configuredSiteOrigin);
  }

  if (process.env.NODE_ENV === 'test') {
    const locationOrigin =
      typeof globalThis.location?.origin === 'string'
        ? globalThis.location.origin.trim()
        : '';
    if (locationOrigin !== '') {
      return normalizeSiteOrigin(locationOrigin);
    }
  }

  throw new Error(`Missing required environment variable: ${SITE_ORIGIN_ENV_NAME}`);
}

export function getSiteOrigin(): string {
  if (!cachedSiteOrigin) {
    cachedSiteOrigin = resolveSiteOrigin();
  }

  return cachedSiteOrigin;
}

export function getSiteHost(): string {
  if (!cachedSiteHost) {
    cachedSiteHost = new URL(getSiteOrigin()).hostname;
  }

  return cachedSiteHost;
}

const DEFAULT_SOCIAL_IMAGE = '/images/seo/siutindei-og-default.jpg';
const DEFAULT_SOCIAL_IMAGE_WIDTH = 1200;
const DEFAULT_SOCIAL_IMAGE_HEIGHT = 630;

function localizePath(path: string, locale: Locale): string {
  return localizeLocalizedPath(path, locale);
}

function buildLocaleAlternates(path: string): Record<string, string> {
  const normalizedPath = normalizeLocalizedPath(path);
  const languages = Object.fromEntries(
    SUPPORTED_LOCALES.map((locale) => [
      locale,
      localizePath(normalizedPath, locale),
    ]),
  );

  return {
    ...languages,
    'x-default': localizePath(normalizedPath, DEFAULT_LOCALE),
  };
}

interface LocalizedMetadataOptions {
  locale: Locale;
  path: string;
  title: string;
  description: string;
  siteName: string;
  socialImage?: {
    url: string;
    alt?: string;
  };
  robots?: {
    index: boolean;
    follow: boolean;
  };
}

function buildPageTitle(title: string, path: string, siteName: string): string {
  const normalizedTitle = title.trim();
  if (normalizedTitle === '') {
    return siteName;
  }

  if (normalizeLocalizedPath(path) === '/') {
    return normalizedTitle;
  }

  const suffix = ` · ${siteName}`;
  if (normalizedTitle.endsWith(suffix)) {
    return normalizedTitle;
  }

  return `${normalizedTitle}${suffix}`;
}

export function buildLocalizedMetadata({
  locale,
  path,
  title,
  description,
  siteName,
  socialImage,
  robots,
}: LocalizedMetadataOptions): Metadata {
  const localizedPath = localizePath(path, locale);
  const pageTitle = buildPageTitle(title, path, siteName);
  const socialImageUrl = socialImage?.url || DEFAULT_SOCIAL_IMAGE;
  const socialImageAlt = socialImage?.alt || siteName;

  return {
    title: pageTitle,
    description,
    alternates: {
      canonical: localizedPath,
      languages: buildLocaleAlternates(path),
    },
    openGraph: {
      title: pageTitle,
      description,
      url: localizedPath,
      siteName,
      type: 'website',
      locale,
      images: [
        {
          url: socialImageUrl,
          alt: socialImageAlt,
          width: DEFAULT_SOCIAL_IMAGE_WIDTH,
          height: DEFAULT_SOCIAL_IMAGE_HEIGHT,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: pageTitle,
      description,
      images: [socialImageUrl],
    },
    robots: {
      index: robots?.index ?? true,
      follow: robots?.follow ?? true,
    },
  };
}
