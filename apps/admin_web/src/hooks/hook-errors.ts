import { ApiError } from '@/lib/api-client-core';

/** Map an API or runtime error to copy for an admin banner. */
export function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return 'The requested resource is not available in this deployment yet.';
    }
    if (error.status === 403) {
      return 'You do not have permission to access this resource.';
    }
    return error.message || fallback;
  }
  return error instanceof Error && error.message ? error.message : fallback;
}
