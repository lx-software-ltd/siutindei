import { buildApiUrl, request } from './api-client-core';

export interface CatalogVersionRow {
  id: string;
  entity_type: string;
  entity_id: string;
  org_id?: string | null;
  version: number;
  action: string;
  snapshot: Record<string, unknown>;
  changed_fields?: string[] | null;
  user_id?: string | null;
  request_id?: string | null;
  import_job_id?: string | null;
  reason?: string | null;
  related_id?: string | null;
  created_at: string;
}

export interface CatalogVersionListResponse {
  items: CatalogVersionRow[];
  next_cursor?: string | null;
}

export interface CatalogVersionFilters {
  entity_type?: string;
  entity_id?: string;
  org_id?: string;
}

export async function listCatalogVersions(
  filters: CatalogVersionFilters,
  limit = 50
): Promise<CatalogVersionListResponse> {
  const url = new URL(buildApiUrl('v1/admin/versions'));
  url.searchParams.set('limit', `${limit}`);
  if (filters.entity_type) {
    url.searchParams.set('entity_type', filters.entity_type);
  }
  if (filters.entity_id) {
    url.searchParams.set('entity_id', filters.entity_id);
  }
  if (filters.org_id) {
    url.searchParams.set('org_id', filters.org_id);
  }
  return request<CatalogVersionListResponse>(url.toString());
}
