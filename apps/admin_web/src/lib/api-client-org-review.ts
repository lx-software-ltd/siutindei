import { buildApiUrl, request } from './api-client-core';

export interface OrgReviewIssue {
  code: string;
  severity: 'blocker' | 'warning';
  entity_type: 'organization' | 'location' | 'activity';
  entity_id: string;
  message: string;
}

export interface OrgReviewListItem {
  id: string;
  name: string;
  status: string;
  review_status: 'pending_review' | 'approved' | 'rejected';
  source?: string | null;
  status_source?: string | null;
  description_source?: string | null;
  import_job_id?: string | null;
  last_imported_at?: string | null;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  place_id?: string | null;
  location_count: number;
  activity_count: number;
  pricing_count: number;
  schedule_count: number;
  issues: OrgReviewIssue[];
  completeness: number;
  blocker_count: number;
  warning_count: number;
}

export interface OrgReviewListResponse {
  items: OrgReviewListItem[];
  next_cursor?: string | null;
}

export interface OrgReviewSummary {
  total: number;
  by_review_status: Record<string, number>;
  by_source: Record<string, number>;
  by_status_source: Record<string, number>;
  by_issue: Record<string, number>;
  with_blockers: number;
}

export interface OrgReviewDetail extends OrgReviewListItem {
  organization: Record<string, unknown>;
  locations: Array<{ id: string; address?: string | null }>;
  activities: Array<{ id: string; name: string }>;
}

export interface OrgReviewFilters {
  review_status?: string;
  status?: string;
  source?: string;
  import_job_id?: string;
  issue?: string;
  has_blockers?: boolean;
  q?: string;
  cursor?: string;
  limit?: number;
}

export interface OrgReviewBulkResult {
  org_id: string;
  status: 'ok' | 'blocked' | 'error';
  review_status?: string;
  message?: string;
  issues?: OrgReviewIssue[];
}

export interface ImportJobListItem {
  id: string;
  object_key: string;
  dry_run: boolean;
  status: string;
  summary: {
    organizations?: { created: number; updated: number; failed: number; skipped: number };
  };
  file_warnings: string[];
  result_count?: number;
  created_at?: string;
  updated_at?: string;
}

const BULK_CHUNK = 200;

export function listOrgReviews(filters: OrgReviewFilters = {}) {
  const url = new URL(buildApiUrl('v1/admin/org-review'));
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    url.searchParams.set(key, String(value));
  });
  return request<OrgReviewListResponse>(url.toString());
}

export function getOrgReviewSummary() {
  return request<OrgReviewSummary>(buildApiUrl('v1/admin/org-review/summary'));
}

export function getOrgReviewDetail(orgId: string) {
  return request<OrgReviewDetail>(buildApiUrl(`v1/admin/org-review/${orgId}`));
}

export function decideOrgReview(
  orgId: string,
  body: {
    action: 'approve' | 'reject' | 'reopen';
    force?: boolean;
    notes?: string;
    status?: string;
  }
) {
  return request<Record<string, unknown>>(
    buildApiUrl(`v1/admin/org-review/${orgId}/decision`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
}

export async function bulkOrgReview(body: {
  org_ids: string[];
  action: 'approve' | 'reject' | 'reopen' | 'set_fields';
  force?: boolean;
  notes?: string;
  status?: string;
  fields?: Record<string, unknown>;
}) {
  const results: OrgReviewBulkResult[] = [];
  for (let index = 0; index < body.org_ids.length; index += BULK_CHUNK) {
    const orgIds = body.org_ids.slice(index, index + BULK_CHUNK);
    const page = await request<{ results: OrgReviewBulkResult[] }>(
      buildApiUrl('v1/admin/org-review/bulk'),
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, org_ids: orgIds }),
      }
    );
    results.push(...page.results);
  }
  return { results };
}

export function listImportJobs(cursor?: string) {
  const url = new URL(buildApiUrl('v1/admin/imports'));
  if (cursor) {
    url.searchParams.set('cursor', cursor);
  }
  return request<{ items: ImportJobListItem[]; next_cursor?: string | null }>(
    url.toString()
  );
}
