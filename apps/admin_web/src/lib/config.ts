export interface AppConfig {
  apiBaseUrl: string;
  cognitoDomain: string;
  cognitoClientId: string;
  cognitoUserPoolId: string;
  publicWwwBaseUrl: string;
  /** Same variable as the public website. Empty hides the catalog map. */
  googleMapsApiKey: string;
  /** Optional Cloud map id. Empty uses Google's demo id for advanced markers. */
  googleMapsMapId: string;
}

const DEFAULT_PUBLIC_WWW_BASE_URL = 'https://siutindei.com';

export const appConfig: AppConfig = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? '',
  cognitoDomain: process.env.NEXT_PUBLIC_COGNITO_DOMAIN ?? '',
  cognitoClientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? '',
  cognitoUserPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? '',
  publicWwwBaseUrl:
    process.env.NEXT_PUBLIC_PUBLIC_WWW_URL ?? DEFAULT_PUBLIC_WWW_BASE_URL,
  googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? '',
  googleMapsMapId: process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID ?? '',
};

function trimTrailingSlashes(value: string) {
  return value.replace(/\/+$/, '');
}

export function getConfigErrors() {
  const errors: string[] = [];
  if (!appConfig.apiBaseUrl) {
    errors.push('NEXT_PUBLIC_API_BASE_URL is missing.');
  }
  if (!appConfig.cognitoDomain) {
    errors.push('NEXT_PUBLIC_COGNITO_DOMAIN is missing.');
  }
  if (!appConfig.cognitoClientId) {
    errors.push('NEXT_PUBLIC_COGNITO_CLIENT_ID is missing.');
  }
  if (!appConfig.cognitoUserPoolId) {
    errors.push('NEXT_PUBLIC_COGNITO_USER_POOL_ID is missing.');
  }
  return errors;
}

export function getCognitoDomain() {
  const trimmed = appConfig.cognitoDomain.trim();
  if (!trimmed) {
    throw new Error('Cognito domain is not configured.');
  }
  const withScheme = trimmed.startsWith('http')
    ? trimmed
    : `https://${trimmed}`;
  return trimTrailingSlashes(withScheme);
}

export function getGoogleMapsApiKey() {
  return appConfig.googleMapsApiKey.trim();
}

/** Advanced markers require a map id. The demo id is Google's published fallback. */
export function getGoogleMapsMapId() {
  return appConfig.googleMapsMapId.trim() || 'DEMO_MAP_ID';
}

export function getApiBaseUrl() {
  const trimmed = appConfig.apiBaseUrl.trim();
  if (!trimmed) {
    throw new Error('API base URL is not configured.');
  }
  return trimTrailingSlashes(trimmed);
}

function getPublicWwwBaseUrl() {
  return trimTrailingSlashes(appConfig.publicWwwBaseUrl.trim());
}

export function getPublicWwwUrl() {
  return getPublicWwwBaseUrl();
}

export function getPrivacyPolicyUrl() {
  return `${getPublicWwwBaseUrl()}/privacy`;
}

export function getTermsOfUseUrl() {
  return `${getPublicWwwBaseUrl()}/terms`;
}
