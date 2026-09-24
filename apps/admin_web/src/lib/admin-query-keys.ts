import type { ApiMode, ResourceType } from '@/lib/resource-api';

/** Cache keys for admin server state. Feature hooks must use these. */
export const adminQueryKeys = {
  resourceList: (resource: ResourceType, mode: ApiMode) =>
    ['admin', 'resource', resource, mode] as const,
  cognitoUsers: () => ['admin', 'cognito-users'] as const,
  tickets: (filters: object) => ['admin', 'tickets', filters] as const,
  auditLogs: (filters: object) => ['admin', 'audit-logs', filters] as const,
  apiKeys: () => ['admin', 'api-keys'] as const,
  categorySuggestions: (filters: object) =>
    ['admin', 'category-suggestions', filters] as const,
  orgReview: (filters: object) => ['admin', 'org-review', filters] as const,
  importJobs: () => ['admin', 'import-jobs'] as const,
};
