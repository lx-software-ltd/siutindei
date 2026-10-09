import { buildApiUrl, request, requestText, type ListResponse } from './api-client-core';

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

export interface LocationFixProposal {
  id: string;
  entity_type: 'organization' | 'activity' | 'location';
  entity_id: string;
  entity_name?: string | null;
  org_id: string;
  org_name?: string | null;
  kind: 'link_existing' | 'create_location' | 'unresolved' | 'update_location';
  target_location_id?: string | null;
  proposed_location?: {
    address?: string;
    area_id?: string;
    area_name?: string;
    lat?: number | null;
    lng?: number | null;
    candidates?: { location_id: string; address?: string | null }[];
    register?: {
      name?: string;
      name_zh?: string;
      school_no?: string;
      category?: string;
      name_similarity?: number;
    };
    lookup?: {
      provider?: string;
      grade?: string;
      display_name?: string;
      district_consistent?: boolean | null;
      other_district?: string | null;
    };
  } | null;
  source: string;
  confidence?: number | null;
  rationale?: string | null;
  status: string;
  current_label: string;
  proposed_label: string;
}

export interface LocationFixSettings {
  monthly_cost_limit_usd: number;
}

export interface LocationScanRun {
  id: string;
  status: string;
  batches_total: number;
  batches_done: number;
  queued_for_model: number;
}

export function listLocationFixes(filters: {
  status?: string;
  entity_type?: string;
  kind?: string;
  source?: string;
  grade?: string;
  org_id?: string;
  q?: string;
  cursor?: string;
  limit?: number;
} = {}) {
  return request<ListResponse<LocationFixProposal>>(
    buildApiUrl(`v1/admin/location-fixes${query(filters)}`)
  );
}

export function exportLocationFixes(filters: {
  status?: string;
  entity_type?: string;
  kind?: string;
  source?: string;
  grade?: string;
  org_id?: string;
  q?: string;
} = {}) {
  return requestText(buildApiUrl(`v1/admin/location-fixes/export${query(filters)}`));
}

export function getLocationFix(id: string) {
  return request<LocationFixProposal>(buildApiUrl(`v1/admin/location-fixes/${id}`));
}

export function getLocationFixSummary() {
  return request<{
    by_status: Record<string, number>;
    pending_by_kind: Record<string, number>;
    month_cost_usd: number;
    monthly_cost_limit_usd: number;
    google_places_configured?: boolean;
    pending_by_grade?: Record<string, number>;
    active_run?: LocationScanRun | null;
  }>(buildApiUrl('v1/admin/location-fixes/summary'));
}

export function getLocationFixSettings() {
  return request<LocationFixSettings>(buildApiUrl('v1/admin/location-fixes/settings'));
}

export function updateLocationFixSettings(body: LocationFixSettings) {
  return request<LocationFixSettings>(buildApiUrl('v1/admin/location-fixes/settings'), {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function scanLocationFixes(body: {
  entity_type?: string;
  q?: string;
  org_id?: string;
  review_scope: 'pending_review' | 'all';
  lookup?: 'nominatim' | 'google';
}) {
  return request<{
    scan_run_id: string;
    created: number;
    updated: number;
    skipped: number;
    cleared: number;
    auto_applied: number;
    queued_for_model: number;
    queued_for_lookup?: number;
    total_entities?: number;
    truncated: boolean;
    status: string;
    error?: string | null;
  }>(buildApiUrl('v1/admin/location-fixes/scan'), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function decideLocationFix(
  id: string,
  body: {
    action: 'apply' | 'dismiss';
    address?: string;
    area_id?: string;
    target_location_id?: string;
    lat?: number;
    lng?: number;
  }
) {
  return request<LocationFixProposal>(buildApiUrl(`v1/admin/location-fixes/${id}`), {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

export function decideLocationFixesBulk(body: {
  action: 'apply' | 'dismiss';
  ids?: string[];
  entity_type?: string;
  kind?: string;
  source?: string;
  grade?: string;
  q?: string;
  org_id?: string;
  dry_run?: boolean;
}) {
  return request<{
    dry_run: boolean;
    matched: number;
    truncated?: boolean;
    decided: number;
    failed: number;
    failures: { id: string; message: string }[];
  }>(buildApiUrl('v1/admin/location-fixes/bulk'), {
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
