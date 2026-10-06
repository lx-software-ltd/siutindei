import { appConfig, getCognitoDomain } from './config';
import { generatePkcePair } from './pkce';

const tokenStorageKey = 'admin_auth_tokens';
const pkceStorageKey = 'admin_auth_pkce';
const loginRedirectStorageKey = 'admin_auth_redirect';

export interface StoredTokens {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  expiresAt: number;
}

export interface UserProfile {
  email?: string;
  groups: string[];
  subject?: string;
  lastAuthTime?: string;
}

interface TokenResponse {
  access_token?: string;
  id_token?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
  error_description?: string;
}

export interface LoginOptions {
  provider?: string;
  returnTo?: string;
}

function loadTokens() {
  if (typeof window === 'undefined') {
    return null;
  }
  const raw = window.localStorage.getItem(tokenStorageKey);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as StoredTokens;
  } catch {
    return null;
  }
}

function storeTokens(tokens: StoredTokens) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(tokenStorageKey, JSON.stringify(tokens));
}

export function storeTokensFromPasswordless(tokens: {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  expiresAt: number;
}) {
  storeTokens({
    accessToken: tokens.accessToken,
    idToken: tokens.idToken,
    refreshToken: tokens.refreshToken,
    expiresAt: tokens.expiresAt,
  });
}

function clearTokens() {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(tokenStorageKey);
}

function storeLoginRedirect(value: string) {
  if (typeof window === 'undefined') {
    return;
  }
  window.sessionStorage.setItem(loginRedirectStorageKey, value);
}

function loadLoginRedirect() {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.sessionStorage.getItem(loginRedirectStorageKey);
}

function clearLoginRedirect() {
  if (typeof window === 'undefined') {
    return;
  }
  window.sessionStorage.removeItem(loginRedirectStorageKey);
}

function resolveReturnTo(returnTo?: string) {
  if (typeof window === 'undefined') {
    return '/';
  }
  if (returnTo && returnTo.startsWith('/')) {
    return returnTo;
  }
  const { pathname, search } = window.location;
  return `${pathname}${search}`;
}

function resolveLoginRedirect() {
  if (typeof window === 'undefined') {
    return '/';
  }
  const stored = loadLoginRedirect();
  clearLoginRedirect();
  return sanitizeLoginRedirect(stored);
}

// CloudFront serves /index.html for /admin/dashboard, so completed
// logins must land on `/` and render the console in place.
export function sanitizeLoginRedirect(stored: string | null): string {
  if (!stored || !stored.startsWith('/')) {
    return '/';
  }
  if (stored.startsWith('/auth/callback')) {
    return '/';
  }
  if (
    stored === '/admin/dashboard' ||
    stored.startsWith('/admin/dashboard/') ||
    stored.startsWith('/admin/dashboard?')
  ) {
    return '/';
  }
  return stored;
}

function getClientId() {
  const clientId = appConfig.cognitoClientId.trim();
  if (!clientId) {
    throw new Error('Cognito client ID is not configured.');
  }
  return clientId;
}

function getRedirectUri() {
  if (typeof window === 'undefined') {
    return '';
  }
  return `${window.location.origin}/auth/callback`;
}

function getLogoutRedirectUri() {
  if (typeof window === 'undefined') {
    return '';
  }
  return `${window.location.origin}/`;
}

// Cognito Hosted UI is cross-origin. Next.js client routing cannot
// complete OAuth; a full document navigation is required.
function assignExternalHttpUrl(url: string) {
  const parsed = new URL(url);
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error('Refusing non-http(s) navigation.');
  }
  window.location.assign(parsed.href);
}

function parseJwt(token: string) {
  const parts = token.split('.');
  if (parts.length < 2) {
    return null;
  }
  const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
  const paddingLength = (4 - (payload.length % 4)) % 4;
  const padded = payload.padEnd(payload.length + paddingLength, '=');
  try {
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getUserProfile(tokens: StoredTokens): UserProfile {
  const payload =
    parseJwt(tokens.idToken) ?? parseJwt(tokens.accessToken) ?? {};
  const email =
    typeof payload.email === 'string' ? payload.email : undefined;
  const subject =
    typeof payload.sub === 'string' ? payload.sub : undefined;
  const groupsValue = payload['cognito:groups'];
  const groups = Array.isArray(groupsValue)
    ? groupsValue.filter((item): item is string => typeof item === 'string')
    : [];

  // Extract auth_time (epoch timestamp in seconds) from the token
  // This is a standard OIDC claim set by Cognito
  let lastAuthTime: string | undefined;
  const authTime = payload.auth_time;
  if (typeof authTime === 'number') {
    try {
      lastAuthTime = new Date(authTime * 1000).toISOString();
    } catch {
      // Invalid timestamp, leave undefined
    }
  }

  return { email, groups, subject, lastAuthTime };
}

export async function startLogin(options?: LoginOptions) {
  if (typeof window === 'undefined') {
    return;
  }
  const returnTo = resolveReturnTo(options?.returnTo);
  storeLoginRedirect(returnTo);
  const { verifier, challenge } = await generatePkcePair();
  window.sessionStorage.setItem(pkceStorageKey, verifier);
  const params = new URLSearchParams({
    client_id: getClientId(),
    response_type: 'code',
    scope: 'openid email profile',
    redirect_uri: getRedirectUri(),
    code_challenge_method: 'S256',
    code_challenge: challenge,
  });
  if (options?.provider) {
    params.set('identity_provider', options.provider);
  }
  const url = `${getCognitoDomain()}/oauth2/authorize?${params}`;
  assignExternalHttpUrl(url);
}

export async function completeLogin() {
  if (typeof window === 'undefined') {
    return '/';
  }
  const url = new URL(window.location.href);
  const code = url.searchParams.get('code');
  if (!code) {
    throw new Error('Authorization code is missing.');
  }
  const verifier = window.sessionStorage.getItem(pkceStorageKey);
  if (!verifier) {
    throw new Error('PKCE verifier is missing.');
  }
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: getClientId(),
    redirect_uri: getRedirectUri(),
    code,
    code_verifier: verifier,
  });
  const response = await fetch(`${getCognitoDomain()}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  const data = (await response.json()) as TokenResponse;
  if (!response.ok) {
    const message =
      data.error_description || data.error || 'Unable to complete login.';
    throw new Error(message);
  }
  if (!data.access_token || !data.id_token) {
    throw new Error('Cognito response missing tokens.');
  }
  const expiresIn = data.expires_in ?? 3600;
  const tokens: StoredTokens = {
    accessToken: data.access_token,
    idToken: data.id_token,
    refreshToken: data.refresh_token,
    expiresAt: Date.now() + expiresIn * 1000,
  };
  storeTokens(tokens);
  window.sessionStorage.removeItem(pkceStorageKey);
  const redirectPath = resolveLoginRedirect();
  window.history.replaceState({}, document.title, url.pathname);
  return redirectPath;
}

export async function ensureFreshTokens() {
  const tokens = loadTokens();
  if (!tokens) {
    return null;
  }
  const now = Date.now();
  if (tokens.expiresAt > now + 60_000) {
    return tokens;
  }
  if (!tokens.refreshToken) {
    clearTokens();
    return null;
  }
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: getClientId(),
    refresh_token: tokens.refreshToken,
  });
  const response = await fetch(`${getCognitoDomain()}/oauth2/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  const data = (await response.json()) as TokenResponse;
  if (!response.ok || !data.access_token) {
    clearTokens();
    return null;
  }
  const expiresIn = data.expires_in ?? 3600;
  const refreshed: StoredTokens = {
    accessToken: data.access_token,
    idToken: data.id_token ?? tokens.idToken,
    refreshToken: data.refresh_token ?? tokens.refreshToken,
    expiresAt: Date.now() + expiresIn * 1000,
  };
  storeTokens(refreshed);
  return refreshed;
}

export function startLogout() {
  if (typeof window === 'undefined') {
    return;
  }
  clearTokens();
  const params = new URLSearchParams({
    client_id: getClientId(),
    logout_uri: getLogoutRedirectUri(),
  });
  const url = `${getCognitoDomain()}/logout?${params}`;
  assignExternalHttpUrl(url);
}
