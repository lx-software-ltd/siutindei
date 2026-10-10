import { ensureFreshTokens } from './auth';
import { getApiBaseUrl } from './config';

export interface ListResponse<T> {
  items: T[];
  next_cursor?: string | null;
}

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export function buildApiUrl(path: string): string {
  const base = getApiBaseUrl();
  const normalized = base.endsWith('/') ? base : `${base}/`;
  return new URL(path, normalized).toString();
}

async function getAuthHeader() {
  const tokens = await ensureFreshTokens();
  if (!tokens) {
    throw new ApiError('Not authenticated.', 401);
  }
  const token = tokens.idToken || tokens.accessToken;
  return { Authorization: `Bearer ${token}` };
}

export async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const authHeader = await getAuthHeader();
  const response = await fetch(url, {
    ...options,
    headers: {
      ...authHeader,
      ...(options.headers ?? {}),
    },
  });

  if (response.status === 204) {
    return null as T;
  }

  const raw = await response.text();
  const data = raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  if (!response.ok) {
    const message =
      data && typeof data === 'object'
        ? (data.error as string | undefined) ||
          (data.message as string | undefined) ||
          response.statusText
        : response.statusText;
    const detail =
      data && typeof data === 'object'
        ? (data.detail as string | undefined)
        : undefined;
    throw new ApiError(message, response.status, detail);
  }

  return data as T;
}
