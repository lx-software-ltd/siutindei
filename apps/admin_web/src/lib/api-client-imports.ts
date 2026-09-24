import { buildApiUrl, request } from './api-client-core';

export type AdminImportRecordType =
  | 'organizations'
  | 'locations'
  | 'activities'
  | 'pricing'
  | 'schedules';

export type AdminImportStatus = 'created' | 'updated' | 'failed' | 'skipped';

export interface AdminImportPresignRequest {
  file_name: string;
  content_type: string;
}

export interface AdminImportPresignResponse {
  upload_url: string;
  object_key: string;
  expires_in: number;
}

export interface AdminImportRequest {
  object_key: string;
}

export interface AdminImportError {
  message: string;
  field?: string | null;
}

export interface AdminImportResult {
  type: AdminImportRecordType;
  key: string;
  status: AdminImportStatus;
  id?: string | null;
  path?: string | null;
  warnings: string[];
  errors: AdminImportError[];
}

export interface AdminImportCounts {
  created: number;
  updated: number;
  failed: number;
  skipped: number;
}

export interface AdminImportSummary {
  organizations: AdminImportCounts;
  locations: AdminImportCounts;
  activities: AdminImportCounts;
  pricing: AdminImportCounts;
  schedules: AdminImportCounts;
  warnings: number;
  errors: number;
}

export interface AdminImportResponse {
  id?: string;
  summary: AdminImportSummary;
  results: AdminImportResult[];
  file_warnings: string[];
}

export interface AdminExportResponse {
  download_url: string;
  object_key: string;
  file_name: string;
  expires_in: number;
  warnings?: string[];
}

function buildAdminImportsUrl(suffix?: string) {
  return suffix ? buildApiUrl(`v1/admin/imports/${suffix}`) : buildApiUrl('v1/admin/imports');
}

export async function createAdminImportPresign(
  payload: AdminImportPresignRequest
) {
  return request<AdminImportPresignResponse>(buildAdminImportsUrl('presign'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function runAdminImport(payload: AdminImportRequest) {
  return request<AdminImportResponse>(buildAdminImportsUrl(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function createAdminExport(orgName?: string) {
  const url = new URL(buildAdminImportsUrl('export'));
  if (orgName) {
    url.searchParams.set('org_name', orgName);
  }
  return request<AdminExportResponse>(url.toString());
}
