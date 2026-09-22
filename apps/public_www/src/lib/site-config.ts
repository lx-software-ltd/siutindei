import buildDefaults from '../../build-env.defaults.json';

interface SiteContact {
  readonly email: string;
  readonly whatsappUrl: string;
  readonly whatsappDisplay: string;
  readonly instagramUrl: string;
}

export interface SearchConfig {
  readonly stagingSearchDataEnabled: boolean;
  readonly stagingSearchFixtureUrl: string;
  readonly apiBaseUrl: string;
  readonly apiKey: string;
  readonly attestationToken: string;
}

export interface SiteConfig {
  readonly siteOrigin: string;
  readonly siteName: string;
  readonly siteTagline: string;
  readonly stagingBadgeEnabled: boolean;
  readonly contact: SiteContact;
  readonly search: SearchConfig;
}

export interface PublicSiteConfig {
  readonly whatsappUrl?: string;
  readonly whatsappDisplay?: string;
  readonly contactEmail?: string;
  readonly instagramUrl?: string;
}

function trimEnv(value: string | undefined): string {
  return (value ?? '').trim();
}

function contactValue(
  envValue: string | undefined,
  fallback: string,
): string {
  return trimEnv(envValue) || fallback;
}

function readBooleanEnv(value: string | undefined): boolean {
  const raw = trimEnv(value).toLowerCase();
  return raw === 'true' || raw === '1' || raw === 'yes';
}

export function getSiteConfig(): SiteConfig {
  return {
    siteOrigin: trimEnv(process.env.NEXT_PUBLIC_SITE_ORIGIN),
    siteName: trimEnv(process.env.NEXT_PUBLIC_SITE_NAME),
    siteTagline: trimEnv(process.env.NEXT_PUBLIC_SITE_TAGLINE),
    stagingBadgeEnabled: readBooleanEnv(
      process.env.NEXT_PUBLIC_STAGING_BADGE_ENABLED,
    ),
    contact: {
      email: contactValue(
        process.env.NEXT_PUBLIC_EMAIL,
        buildDefaults.contactEmail,
      ),
      whatsappUrl: contactValue(
        process.env.NEXT_PUBLIC_WHATSAPP_URL,
        buildDefaults.whatsappUrl,
      ),
      whatsappDisplay: buildDefaults.whatsappDisplay,
      instagramUrl: trimEnv(process.env.NEXT_PUBLIC_INSTAGRAM_URL),
    },
    search: getSearchConfig(),
  };
}

export function getSearchConfig(): SearchConfig {
  const stagingSearchDataEnabled = readBooleanEnv(
    process.env.NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED,
  );
  const siteOrigin = trimEnv(process.env.NEXT_PUBLIC_SITE_ORIGIN).replace(
    /\/$/,
    '',
  );
  const explicitFixtureUrl = trimEnv(
    process.env.NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL,
  );
  const stagingSearchFixtureUrl =
    explicitFixtureUrl
    || (stagingSearchDataEnabled && siteOrigin
      ? `${siteOrigin}/fixtures/activity_search_staging.json`
      : '');

  return {
    stagingSearchDataEnabled,
    stagingSearchFixtureUrl,
    apiBaseUrl: trimEnv(process.env.NEXT_PUBLIC_SEARCH_API_BASE_URL),
    apiKey: trimEnv(process.env.NEXT_PUBLIC_SEARCH_API_KEY),
    attestationToken: trimEnv(process.env.NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN),
  };
}

export function getCopyrightYear(): number {
  const raw = trimEnv(process.env.NEXT_PUBLIC_BUILD_YEAR);
  const parsed = Number.parseInt(raw, 10);
  if (Number.isFinite(parsed) && parsed >= 2000 && parsed <= 2100) {
    return parsed;
  }

  return new Date().getFullYear();
}

export function getGoogleMapsApiKey(): string {
  return trimEnv(process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY);
}

export function getGtmId(): string {
  return trimEnv(process.env.NEXT_PUBLIC_GTM_ID);
}

export function getGtmAllowedHosts(): string {
  return trimEnv(process.env.NEXT_PUBLIC_GTM_ALLOWED_HOSTS);
}

export function getMetaPixelId(): string {
  return trimEnv(process.env.NEXT_PUBLIC_META_PIXEL_ID);
}

export function getMetaPixelAllowedHosts(): string {
  return trimEnv(process.env.NEXT_PUBLIC_META_PIXEL_ALLOWED_HOSTS);
}

export function resolvePublicSiteConfig(): PublicSiteConfig {
  const { email, whatsappUrl, whatsappDisplay, instagramUrl } =
    getSiteConfig().contact;

  return {
    ...(whatsappUrl ? { whatsappUrl } : {}),
    ...(whatsappDisplay ? { whatsappDisplay } : {}),
    ...(email ? { contactEmail: email } : {}),
    ...(instagramUrl ? { instagramUrl } : {}),
  };
}
