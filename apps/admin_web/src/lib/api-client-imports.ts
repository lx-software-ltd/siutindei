import { buildApiUrl, request } from './api-client-core';

export type AdminImportRecordType =
  | 'organizations'
  | 'locations'
  | 'activities'
  | 'pricing'
  | 'schedules';

export type AdminImportStatus =
  | 'created'
  | 'updated'
  | 'unchanged'
  | 'failed'
  | 'skipped';

export interface AdminImportPresignRequest {
  file_name: string;
  content_type: string;
}

export interface AdminImportPresignResponse {
  upload_url: string;
  object_key: string;
  expires_in: number;
}

export type NameCleanupMode = 'off' | 'propose' | 'apply';
export type UnknownCategoryMode = 'capture' | 'fail';
export type DuplicateCheckMode = 'off' | 'report';
export type ScanCheckMode = 'off' | 'check';

export interface ImportSettings {
  skip_deleted_organizations: boolean;
  name_cleanup: NameCleanupMode;
  unknown_categories: UnknownCategoryMode;
  duplicates: DuplicateCheckMode;
  locations: ScanCheckMode;
  categories: ScanCheckMode;
  updated_by?: string | null;
  updated_at: string | null;
}

export interface AdminImportRequest {
  object_key?: string;
  dry_run?: boolean;
  retry_failed?: boolean;
  allow_updates?: boolean;
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
  unchanged?: number;
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
  captured_categories?: number;
  captured_category_ids?: string[];
  data_quality_run_id?: string;
}

export interface AdminImportResponse {
  id?: string;
  summary: AdminImportSummary;
  results: AdminImportResult[];
  file_warnings: string[];
  source?: 'ui' | 'board' | null;
  data_quality_run_id?: string | null;
}

export interface AdminImportJob {
  id: string;
  object_key: string;
  download_url?: string;
  dry_run: boolean;
  allow_updates?: boolean;
  source?: 'ui' | 'board' | null;
  status?: string;
  summary: AdminImportSummary;
  results: AdminImportResult[];
  file_warnings: string[];
  created_at?: string;
  updated_at?: string;
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

export async function getAdminImportJob(jobId: string) {
  return request<AdminImportJob>(buildAdminImportsUrl(jobId));
}

export async function getImportSettings() {
  return request<ImportSettings>(buildApiUrl('v1/admin/import-settings'));
}

export async function updateImportSettings(payload: ImportSettings) {
  return request<ImportSettings>(buildApiUrl('v1/admin/import-settings'), {
    method: 'PUT',
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
