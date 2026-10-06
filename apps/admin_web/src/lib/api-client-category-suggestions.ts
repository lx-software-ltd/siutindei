import { buildApiUrl, request } from './api-client-core';

export interface CategorySuggestion {
  id: string;
  fingerprint: string;
  requested_name: string;
  source: string;
  status: 'pending' | 'approved' | 'merged' | 'rejected';
  enrichment_status: 'none' | 'queued' | 'running' | 'done' | 'failed';
  enrichment_error?: string | null;
  enriched_at?: string | null;
  model_used?: string | null;
  suggested_name?: string | null;
  name_translations?: Record<string, string>;
  suggested_parent_id?: string | null;
  maps_to_category_id?: string | null;
  confidence?: number | null;
  rationale?: string | null;
  alternatives?: {
    items?: Array<{
      name_en?: string | null;
      parent_id?: string | null;
      confidence?: number | null;
    }>;
    display_order_hint?: number;
  };
  usage?: { cost_usd?: number; prompt_tokens?: number; completion_tokens?: number };
  created_category_id?: string | null;
  merged_into_category_id?: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
  decision_notes?: string | null;
  activity_count: number;
  reopened_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  activities?: CategorySuggestionActivityLink[];
}

export interface CategorySuggestionActivityLink {
  activity_id: string;
  activity_name?: string;
  org_id: string;
  org_name?: string;
  import_job_id?: string | null;
  requested_name: string;
  created_at?: string | null;
}

export interface CategorySuggestionSummary {
  by_status: Record<string, number>;
  by_enrichment_status: Record<string, number>;
  pending_activity_total: number;
  stranded_activity_total: number;
  month_cost_usd: number;
  review_pending_total?: number;
  auto_applied_total?: number;
  scan_candidate_total?: number;
  scan_limit?: number;
  scan_batch_size?: number;
  discover_activity_total?: number;
  discover_label_total?: number;
  active_scan_run?: CategoryScanRun | null;
}

export interface CategorySuggestionSettings {
  on_import_enabled: boolean;
  auto_enrich_enabled: boolean;
  openrouter_model?: string | null;
  default_openrouter_model?: string;
  fallback_models: string[];
  max_evidence_items: number;
  deny_data_collection: boolean;
  auto_assign_threshold?: number | null;
  monthly_cost_limit_usd?: number;
  updated_by?: string | null;
  updated_at?: string | null;
}

export interface CategorySuggestionFilters {
  status?: string;
  enrichment_status?: string;
  import_job_id?: string;
  source?: string;
  q?: string;
  cursor?: string;
  limit?: number;
}

export interface CategoryScanRun {
  id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  requested_by?: string | null;
  org_id?: string | null;
  mode?: 'verify' | 'discover';
  ignore_current_category?: boolean;
  batch_size: number;
  total_activities: number;
  labels_total?: number;
  batches_total: number;
  batches_done: number;
  confirmed: number;
  auto_applied: number;
  reassign_pending: number;
  proposed: number;
  skipped: number;
  failed: number;
  cost_usd: number;
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  finished_at?: string | null;
}

export interface ActivityCategoryReview {
  id: string;
  scan_run_id: string;
  activity_id: string;
  activity_name?: string;
  org_id: string;
  org_name?: string;
  current_category_id?: string | null;
  current_category_name?: string | null;
  verdict: 'confirm' | 'reassign' | 'propose';
  proposed_category_id?: string | null;
  proposed_category_name?: string | null;
  suggestion_id?: string | null;
  confidence?: number | null;
  rationale?: string | null;
  status: string;
  previous_category_id?: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
  created_at?: string | null;
}

export interface CategoryReviewFilters {
  status?: string;
  verdict?: string;
  org_id?: string;
  scan_run_id?: string;
  proposed_category_id?: string;
  q?: string;
  cursor?: string;
  limit?: number;
}

function suggestionUrl(suffix = '') {
  return buildApiUrl(`v1/admin/category-suggestions${suffix}`);
}

export function listCategorySuggestions(filters: CategorySuggestionFilters = {}) {
  const url = new URL(suggestionUrl());
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    url.searchParams.set(key, String(value));
  });
  return request<{ items: CategorySuggestion[]; next_cursor?: string | null }>(
    url.toString()
  );
}

export function getCategorySuggestionSummary(orgId?: string) {
  const url = new URL(suggestionUrl('/summary'));
  if (orgId) {
    url.searchParams.set('org_id', orgId);
  }
  return request<CategorySuggestionSummary>(url.toString());
}

export function getCategorySuggestion(id: string) {
  return request<CategorySuggestion>(suggestionUrl(`/${id}`));
}

export function decideCategorySuggestion(
  id: string,
  body: Record<string, unknown>
) {
  return request<CategorySuggestion>(suggestionUrl(`/${id}/decision`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function enrichCategorySuggestion(id: string) {
  return request<{ id: string; status: string }>(suggestionUrl(`/${id}/enrich`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
}

export function getCategorySuggestionSettings() {
  return request<CategorySuggestionSettings>(suggestionUrl('/settings'));
}

export function updateCategorySuggestionSettings(
  body: Partial<CategorySuggestionSettings>
) {
  return request<CategorySuggestionSettings>(suggestionUrl('/settings'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function startCategoryScan(body: {
  org_id?: string;
  limit?: number;
  batch_size?: number;
  rescan?: boolean;
  mode?: 'verify' | 'discover';
  ignore_current_category?: boolean;
} = {}) {
  return request<CategoryScanRun>(suggestionUrl('/scan'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function listCategoryScanRuns() {
  return request<{ items: CategoryScanRun[] }>(suggestionUrl('/scan'));
}

export function getCategoryScanRun(id: string) {
  return request<CategoryScanRun>(suggestionUrl(`/scan/${id}`));
}

export function listCategoryReviews(filters: CategoryReviewFilters = {}) {
  const url = new URL(suggestionUrl('/reviews'));
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') {
      return;
    }
    url.searchParams.set(key, String(value));
  });
  return request<{ items: ActivityCategoryReview[]; next_cursor?: string | null }>(
    url.toString()
  );
}

export function getCategoryReview(id: string) {
  return request<ActivityCategoryReview>(suggestionUrl(`/reviews/${id}`));
}

export function decideCategoryReview(id: string, body: Record<string, unknown>) {
  return request<ActivityCategoryReview>(suggestionUrl(`/reviews/${id}`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function testCategorySuggestionModel(model?: string) {
  return request<{ ok: boolean; message: string }>(suggestionUrl('/settings/test'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model ? { model } : {}),
  });
}
