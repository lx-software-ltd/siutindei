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
  categoryReviews: () => ['admin', 'category-reviews'] as const,
  orgReview: () => ['admin', 'org-review'] as const,
  orgReviewMap: () => ['admin', 'org-review-map'] as const,
  orgDuplicates: () => ['admin', 'org-duplicates'] as const,
  deletedOrganizations: () => ['admin', 'deleted-organizations'] as const,
  nameFixes: () => ['admin', 'name-fixes'] as const,
  locationFixes: () => ['admin', 'location-fixes'] as const,
  translationFixes: () => ['admin', 'translation-fixes'] as const,
  importJobs: () => ['admin', 'import-jobs'] as const,
  importJob: (id: string) => ['admin', 'import-jobs', id] as const,
  importSettings: () => ['admin', 'import-settings'] as const,
  dataQualityRuns: () => ['admin', 'data-quality-runs'] as const,
  dataQualityRun: (id: string) => ['admin', 'data-quality-runs', id] as const,
  catalogVersions: () => ['admin', 'catalog-versions'] as const,
  orgEnrichment: (orgId: string) => ['admin', 'org-enrichment', orgId] as const,
};
