import { buildApiUrl, request } from './api-client-core';

export interface EnrichmentRun {
  id: string;
  org_id: string;
  status: string;
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
  venues: Array<{ id: string; address: string }>;
}

export function getOrgEnrichment(orgId: string): Promise<EnrichmentRead> {
  return request<EnrichmentRead>(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment`)
  );
}

export function startOrgEnrichment(orgId: string): Promise<{ run: EnrichmentRun }> {
  return request<{ run: EnrichmentRun }>(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment`),
    { method: 'POST', headers: { 'Content-Type': 'application/json' } }
  );
}

export function decideOrgEnrichment(
  orgId: string,
  action: 'apply' | 'dismiss',
  ids: string[]
): Promise<{ results: Array<{ id: string; status: string; error?: string }> }> {
  return request(
    buildApiUrl(`v1/admin/organizations/${orgId}/enrichment/${action}`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    }
  );
}
