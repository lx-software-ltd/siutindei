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
  blocking?: boolean;
}

export async function listCatalogVersions(
  filters: CatalogVersionFilters,
  limit = 50,
  cursor?: string
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
  if (filters.blocking) {
    url.searchParams.set('blocking', 'true');
  }
  if (cursor) {
    url.searchParams.set('cursor', cursor);
  }
  return request<CatalogVersionListResponse>(url.toString());
}

/** Follow the cursor so a long history still includes version 1. */
export async function listEntireCatalogHistory(
  filters: CatalogVersionFilters
): Promise<CatalogVersionListResponse> {
  const items: CatalogVersionRow[] = [];
  let cursor: string | undefined;
  let next: string | null = null;
  for (let page = 0; page < 25; page += 1) {
    const response = await listCatalogVersions(filters, 200, cursor);
    items.push(...response.items);
    next = response.next_cursor ?? null;
    if (!next) {
      break;
    }
    cursor = next;
  }
  return { items, next_cursor: next };
}

export function forgetCatalogVersion(id: string) {
  return request<void>(buildApiUrl(`v1/admin/versions/${id}/forget`), {
    method: 'POST',
  });
}
