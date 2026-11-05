import { buildApiUrl, request } from './api-client-core';

export interface ImportChange {
  id: string;
  entity_type: string;
  entity_id: string;
  org_id?: string | null;
  org_name?: string | null;
  record_name: string;
  field: string;
  base_value?: unknown;
  current_value?: unknown;
  proposed_value?: unknown;
  import_job_id?: string | null;
  created_at: string;
  current_user_id?: string | null;
  current_import_job_id?: string | null;
  status: 'pending' | 'applied' | 'dismissed';
}

export interface ImportChangeList {
  items: ImportChange[];
  next_cursor?: string | null;
  pending_count: number;
}

export function listImportChanges(params: {
  orgId?: string;
  importJobId?: string;
  cursor?: string;
  limit?: number;
}): Promise<ImportChangeList> {
  const search = new URLSearchParams();
  if (params.orgId) {
    search.set('org_id', params.orgId);
  }
  if (params.importJobId) {
    search.set('import_job_id', params.importJobId);
  }
  if (params.cursor) {
    search.set('cursor', params.cursor);
  }
  if (params.limit) {
    search.set('limit', String(params.limit));
  }
  const query = search.toString();
  const path = query
    ? `v1/admin/import-changes?${query}`
    : 'v1/admin/import-changes';
  return request<ImportChangeList>(buildApiUrl(path));
}

export function acceptImportChange(id: string): Promise<ImportChange> {
  return request<ImportChange>(
    buildApiUrl(`v1/admin/import-changes/${id}/accept`),
    { method: 'POST', body: JSON.stringify({}) }
  );
}

export function dismissImportChange(id: string): Promise<ImportChange> {
  return request<ImportChange>(
    buildApiUrl(`v1/admin/import-changes/${id}/dismiss`),
    { method: 'POST', body: JSON.stringify({}) }
  );
}

export function acceptAllImportChanges(body: {
  org_id?: string;
  import_job_id?: string;
}): Promise<{ applied: number }> {
  return request<{ applied: number }>(
    buildApiUrl('v1/admin/import-changes/accept-all'),
    { method: 'POST', body: JSON.stringify(body) }
  );
}

export function importChangeCount(orgId: string): Promise<number> {
  return listImportChanges({ orgId, limit: 1 }).then((page) => page.pending_count);
}
