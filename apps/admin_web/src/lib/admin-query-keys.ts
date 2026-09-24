import type { ApiMode, ResourceType } from '@/lib/resource-api';

/** Cache keys for admin server state. Feature hooks must use these. */
export const adminQueryKeys = {
  resourceList: (resource: ResourceType, mode: ApiMode) =>
    ['admin', 'resource', resource, mode] as const,
  cognitoUsers: () => ['admin', 'cognito-users'] as const,
  tickets: () => ['admin', 'tickets'] as const,
  auditLogs: () => ['admin', 'audit-logs'] as const,
  apiKeys: () => ['admin', 'api-keys'] as const,
  categorySuggestions: () => ['admin', 'category-suggestions'] as const,
  orgReview: () => ['admin', 'org-review'] as const,
  importJobs: () => ['admin', 'import-jobs'] as const,
};
