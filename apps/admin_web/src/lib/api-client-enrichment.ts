import { buildApiUrl, request } from './api-client-core';

export interface EnrichmentRun {
  id: string;
  org_id: string;
  status: string;
  source?: string;
  seed_url: string;
  pages_fetched: number;
  bytes_fetched: number;
  model: string | null;
  cost_usd: number;
  error: string | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface EnrichmentProposal {
  id: string;
  section: string;
  kind: string;
  field: string | null;
  label: string;
  current_value: Record<string, unknown> | null;
  proposed_value: Record<string, unknown>;
  confidence: number;
  unverified: boolean;
  evidence: Array<{ url?: string; quote?: string }>;
  status: string;
  copyright_notice?: string | null;
}

export interface EnrichmentRead {
  run: EnrichmentRun | null;
  proposals: EnrichmentProposal[];
  venues: Array<{
    id: string;
    address: string;
    name?: string | null;
    status?: string | null;
  }>;
}

export function getOrgEnrichment(orgId: string): Promise<EnrichmentRead> {
  return request<EnrichmentRead>(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment`)
  );
}

export type LeafletStartItem = { url: string } | { object_key: string };

export function startOrgEnrichment(
  orgId: string,
  websiteOrLeaflet?: string | { leaflet: { items: LeafletStartItem[] } }
): Promise<{ run: EnrichmentRun }> {
  const body =
    typeof websiteOrLeaflet === 'string'
      ? websiteOrLeaflet
        ? { website: websiteOrLeaflet }
        : {}
      : (websiteOrLeaflet ?? {});
  return request<{ run: EnrichmentRun }>(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }
  );
}

export interface LeafletUpload {
  upload_url: string;
  media_url: string;
  object_key: string;
  content_type: string;
  expires_in: number;
}

export function createLeafletUpload(
  orgId: string,
  fileName: string,
  contentType: string
): Promise<LeafletUpload> {
  return request<LeafletUpload>(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment/leaflet-upload`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: fileName, content_type: contentType }),
    }
  );
}

export interface EnrichmentOverride {
  area_id?: string;
  category_id?: string;
  age_min?: number;
  age_max?: number;
  location_id?: string;
}

export interface EnrichmentSettings {
  monthly_cost_limit_usd: number;
  max_pages: number;
  max_page_bytes: number;
  copy_media: boolean;
  min_confidence_shown: number;
  leaflet_model: string | null;
}

export function decideOrgEnrichment(
  orgId: string,
  action: 'apply' | 'dismiss',
  ids: string[],
  overrides?: Record<string, EnrichmentOverride>
): Promise<{
  results: Array<{ id: string; status: string; error?: string }>;
  data_quality_run_id?: string;
}> {
  return request(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment/${action}`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        action === 'apply' ? { ids, overrides: overrides ?? {} } : { ids }
      ),
    }
  );
}

export function getEnrichmentSettings(): Promise<EnrichmentSettings> {
  return request<EnrichmentSettings>(buildApiUrl('v1/admin/enrichment-settings'));
}

export function updateEnrichmentSettings(
  body: EnrichmentSettings
): Promise<EnrichmentSettings> {
  return request<EnrichmentSettings>(buildApiUrl('v1/admin/enrichment-settings'), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
