import { buildApiUrl, request, type ListResponse } from './api-client-core';

export interface OrgDuplicateMember {
  id: string;
  name: string;
  review_status: string;
  status: string;
  source?: string | null;
  source_id?: string | null;
  place_id?: string | null;
  manager_id?: string;
  phone_number?: string | null;
  email?: string | null;
  location_count?: number;
  activity_count?: number;
}

export interface OrgDuplicateGroup {
  id: string;
  score: number;
  signals: string[];
  suggested_survivor_id: string;
  organizations: OrgDuplicateMember[];
}

export interface OrgDuplicateFilters {
  min_score?: number;
  signal?: string;
  source?: string;
  review_status?: string;
  q?: string;
  org_id?: string;
  cursor?: string;
  limit?: number;
}

export interface OrgMergeField {
  field: string;
  label: string;
  survivor_value?: string | null;
  source_values: { id: string; name: string; value: string }[];
  result?: string | null;
  conflict: boolean;
}

export interface OrgMergeResult {
  survivor_id: string;
  source_ids: string[];
  suggested_survivor_id: string;
  fields: OrgMergeField[];
  moved: Record<string, number>;
  warnings: string[];
  media_urls?: string[];
  dry_run: boolean;
  merged?: boolean;
}

export interface NameFixProposal {
  id: string;
  entity_type: 'organization' | 'activity';
  entity_id: string;
  current_value: string;
  proposed_value: string;
  rules: string[];
  translation_patch?: Record<string, string> | null;
  status: string;
}

export interface NameFixSettings {
  enabled_rules: string[];
  available_rules?: string[];
  exception_words: string[];
  bracket_suffixes: string[];
}

const jsonHeaders = { 'Content-Type': 'application/json' };

function query(params: object) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export function listOrgDuplicates(filters: OrgDuplicateFilters = {}) {
  return request<{ items: OrgDuplicateGroup[]; next_cursor?: string | null; truncated?: boolean }>(
    buildApiUrl(`v1/admin/org-duplicates${query(filters)}`)
  );
}

export function getOrgDuplicate(id: string) {
  return request<OrgDuplicateGroup>(
    buildApiUrl(`v1/admin/org-duplicates/${encodeURIComponent(id)}`)
  );
}

export function searchOrganizationsForMerge(q: string) {
  return request<{ items: OrgDuplicateMember[] }>(
    buildApiUrl(`v1/admin/org-duplicates/search${query({ q })}`)
  );
}

export function dismissOrgDuplicates(orgIds: string[]) {
  return request<{ dismissed_pairs: number }>(
    buildApiUrl('v1/admin/org-duplicates/dismiss'),
    {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ org_ids: orgIds }),
    }
  );
}

export function mergeOrganizations(body: {
  survivor_id: string;
  source_ids: string[];
  dry_run?: boolean;
  field_overrides?: Record<string, string>;
}) {
  return request<OrgMergeResult>(buildApiUrl('v1/admin/org-duplicates/merge'), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function listNameFixes(filters: {
  status?: string;
  entity_type?: string;
  rule?: string;
  org_id?: string;
  q?: string;
  cursor?: string;
  limit?: number;
} = {}) {
  return request<ListResponse<NameFixProposal>>(
    buildApiUrl(`v1/admin/name-fixes${query(filters)}`)
  );
}

export function getNameFix(id: string) {
  return request<NameFixProposal>(buildApiUrl(`v1/admin/name-fixes/${id}`));
}

export function getNameFixSummary() {
  return request<{
    by_status: Record<string, number>;
    pending_by_entity: Record<string, number>;
  }>(buildApiUrl('v1/admin/name-fixes/summary'));
}

export function getNameFixSettings() {
  return request<NameFixSettings>(buildApiUrl('v1/admin/name-fixes/settings'));
}

export function updateNameFixSettings(body: NameFixSettings) {
  return request<NameFixSettings>(buildApiUrl('v1/admin/name-fixes/settings'), {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function scanNameFixes(
  body: {
    entity_type?: string;
    q?: string;
    review_scope: 'pending_review' | 'all';
  }
) {
  return request<{
    scan_run_id: string;
    created: number;
    updated: number;
    skipped: number;
    cleared: number;
    truncated: boolean;
  }>(buildApiUrl('v1/admin/name-fixes/scan'), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function decideNameFix(id: string, body: { action: 'apply' | 'dismiss'; value?: string }) {
  return request<NameFixProposal>(buildApiUrl(`v1/admin/name-fixes/${id}`), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function decideNameFixesBulk(body: {
  action: 'apply' | 'dismiss';
  ids?: string[];
  entity_type?: string;
  rule?: string;
  q?: string;
  org_id?: string;
  dry_run?: boolean;
}) {
  return request<{
    dry_run: boolean;
    matched: number;
    decided: number;
    failed: number;
    failures: { id: string; message: string }[];
  }>(buildApiUrl('v1/admin/name-fixes/bulk'), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}
