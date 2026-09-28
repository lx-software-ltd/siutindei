'use client';

import { useMemo, useState } from 'react';
import { useQueryState } from 'nuqs';

import { useOrganizationsByMode } from '../../hooks/use-organizations-by-mode';
import {
  ApiError,
  createAdminExport,
  createAdminImportPresign,
  runAdminImport,
  type AdminImportResponse,
} from '../../lib/api-client';
import { AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminTabStrip } from '../ui/admin-tab-strip';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { FileUploadButton } from '../ui/file-upload-button';
import { Select } from '../ui/select';
import { StatusBanner } from '../status-banner';
import { ImportHistoryPanel } from './org-review/import-history-panel';
import { ReviewQueuePanel } from './org-review/review-queue-panel';

type ImportTab = 'import' | 'review' | 'history';
type ImportStatus = 'idle' | 'uploading' | 'processing' | 'done' | 'error';
type ExportStatus = 'idle' | 'loading' | 'done' | 'error';
type ExportTarget = 'all' | 'selected';

const IMPORT_TABS: { key: ImportTab; label: string }[] = [
  { key: 'import', label: 'Import' },
  { key: 'review', label: 'Review' },
  { key: 'history', label: 'History' },
];

const emptyImportSummary = {
  created: 0,
  updated: 0,
  failed: 0,
  skipped: 0,
};

function formatCountLabel(counts: typeof emptyImportSummary) {
  return `created ${counts.created}, updated ${counts.updated}, ` +
    `failed ${counts.failed}, skipped ${counts.skipped}`;
}

function formatErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

function downloadFile(url: string, fileName: string) {
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.rel = 'noreferrer';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export function ImportsPanel() {
  const [tabParam, setTabParam] = useQueryState('tab');
  const [, setJobParam] = useQueryState('job');
  const activeTab: ImportTab =
    tabParam === 'review' || tabParam === 'history' ? tabParam : 'import';
  const {
    items: organizations,
    isLoading: isOrgLoading,
    error: orgError,
  } = useOrganizationsByMode('admin', { limit: 200, fetchAll: true });

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importTouched, setImportTouched] = useState(false);
  const [importStatus, setImportStatus] = useState<ImportStatus>('idle');
  const [importError, setImportError] = useState('');
  const [importResult, setImportResult] = useState<AdminImportResponse | null>(
    null
  );

  const [selectedOrgName, setSelectedOrgName] = useState('');
  const [exportStatus, setExportStatus] = useState<ExportStatus>('idle');
  const [exportTarget, setExportTarget] = useState<ExportTarget | null>(null);
  const [exportError, setExportError] = useState('');
  const [exportWarnings, setExportWarnings] = useState<string[]>([]);

  const isImportBusy =
    importStatus === 'uploading' || importStatus === 'processing';
  const isExportBusy = exportStatus === 'loading';

  const showImportFileError = importTouched && !selectedFile;
  const importFileError = showImportFileError
    ? 'Select a JSON file to upload.'
    : '';

  const failedResults = useMemo(() => {
    return importResult?.results.filter((result) =>
      result.errors.length > 0
    ) ?? [];
  }, [importResult]);

  const warningResults = useMemo(() => {
    return importResult?.results.filter((result) =>
      result.warnings.length > 0
    ) ?? [];
  }, [importResult]);

  async function uploadImportFile(
    uploadUrl: string,
    file: File,
    contentType: string
  ) {
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': contentType,
      },
      body: file,
    });
    if (!response.ok) {
      throw new Error('Upload failed. Please try again.');
    }
  }

  async function handleImport() {
    if (!selectedFile) {
      setImportTouched(true);
      setImportError('Select a JSON file to upload.');
      return;
    }

    setImportError('');
    setImportResult(null);
    setImportStatus('uploading');

    try {
      const contentType = selectedFile.type || 'application/json';
      const presign = await createAdminImportPresign({
        file_name: selectedFile.name,
        content_type: contentType,
      });
      await uploadImportFile(presign.upload_url, selectedFile, contentType);
      setImportStatus('processing');
      const result = await runAdminImport({
        object_key: presign.object_key,
      });
      setImportResult(result);
      setImportStatus('done');
    } catch (error) {
      setImportError(
        formatErrorMessage(error, 'Import failed. Please try again.')
      );
      setImportStatus('error');
    }
  }

  async function handleExport(orgName?: string) {
    setExportTarget(orgName ? 'selected' : 'all');
    setExportError('');
    setExportWarnings([]);
    setExportStatus('loading');
    try {
      const response = await createAdminExport(orgName);
      if (response.warnings?.length) {
        setExportWarnings(response.warnings);
      }
      downloadFile(response.download_url, response.file_name);
      setExportStatus('done');
    } catch (error) {
      setExportError(
        formatErrorMessage(error, 'Export failed. Please try again.')
      );
      setExportStatus('error');
    }
  }

  const importLoadingLabel =
    importStatus === 'processing' ? 'Processing…' : 'Uploading…';

  return (
    <div className='space-y-6'>
      <AdminTabStrip
        aria-label='Imports'
        items={IMPORT_TABS}
        activeKey={activeTab}
        onChange={(key) => {
          void setTabParam(key === 'import' ? null : key);
        }}
      />
      {activeTab === 'review' && <ReviewQueuePanel />}
      {activeTab === 'history' && <ImportHistoryPanel />}
      {activeTab === 'import' && (
        <>
          <Card>
            <h2 className='sr-only'>Imports</h2>
            <AdminEditorPanel
              status={
                importError ? (
                  <StatusBanner variant='error' title='Import error'>
                    {importError}
                  </StatusBanner>
                ) : null
              }
              actions={
                <Button
                  type='button'
                  onClick={() => {
                    void handleImport();
                  }}
                  disabled={!selectedFile}
                  loading={isImportBusy}
                  loadingLabel={importLoadingLabel}
                >
                  Upload & Import
                </Button>
              }
            >
              <p className='text-sm text-slate-600'>
                Upload a JSON file to upsert organizations and related data.
              </p>
              <AdminFieldGrid columns={1}>
                <AdminField
                  label='JSON file'
                  htmlFor='admin-import-file'
                  required
                  error={importFileError || undefined}
                >
                  <FileUploadButton
                    id='admin-import-file'
                    accept='application/json,.json'
                    onChange={(event) => {
                      setImportTouched(true);
                      setSelectedFile(event.target.files?.[0] ?? null);
                    }}
                    buttonLabel='Choose file'
                    selectedFileName={selectedFile?.name ?? null}
                    emptyLabel='No file selected'
                    fileNameClassName={
                      showImportFileError ? 'text-red-600' : 'text-slate-600'
                    }
                  />
                </AdminField>
              </AdminFieldGrid>
            </AdminEditorPanel>
            {importResult && (
              <div className='mt-4 space-y-4 rounded-lg border border-slate-200 p-4'>
                {importResult.id &&
                  importResult.summary.organizations.created > 0 && (
                    <Button
                      type='button'
                      variant='secondary'
                      onClick={() => {
                        void setJobParam(importResult.id ?? null);
                        void setTabParam('review');
                      }}
                    >
                      Review organizations from this import
                    </Button>
                  )}
                <div className='space-y-1 text-sm text-slate-700'>
                  <p className='font-semibold text-slate-900'>Summary</p>
                  <p>
                    Organizations:{' '}
                    {formatCountLabel(importResult.summary.organizations)}
                  </p>
                  <p>
                    Locations: {formatCountLabel(importResult.summary.locations)}
                  </p>
                  <p>
                    Activities:{' '}
                    {formatCountLabel(importResult.summary.activities)}
                  </p>
                  <p>Pricing: {formatCountLabel(importResult.summary.pricing)}</p>
                  <p>
                    Schedules: {formatCountLabel(importResult.summary.schedules)}
                  </p>
                  <p>
                    Warnings: {importResult.summary.warnings}, Errors:{' '}
                    {importResult.summary.errors}
                  </p>
                </div>
                {importResult.file_warnings.length > 0 && (
                  <div className='space-y-1 text-sm text-slate-600'>
                    <p className='font-semibold text-slate-900'>
                      File warnings
                    </p>
                    <ul className='list-disc space-y-1 pl-5'>
                      {importResult.file_warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {warningResults.length > 0 && (
                  <div className='space-y-1 text-sm text-slate-600'>
                    <p className='font-semibold text-slate-900'>
                      Record warnings
                    </p>
                    <ul className='list-disc space-y-1 pl-5'>
                      {warningResults.map((result, index) => (
                        <li key={`${result.key}-${index}`}>
                          <span className='font-medium text-slate-800'>
                            {result.type}
                          </span>{' '}
                          {result.key}: {result.warnings.join('; ')}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {failedResults.length > 0 && (
                  <div className='space-y-1 text-sm text-red-700'>
                    <p className='font-semibold text-red-900'>Errors</p>
                    <ul className='list-disc space-y-1 pl-5'>
                      {failedResults.map((result, index) => (
                        <li key={`${result.key}-${index}`}>
                          <span className='font-medium'>{result.type}</span>{' '}
                          {result.key}:{' '}
                          {result.errors
                            .map((err) => err.message)
                            .join('; ')}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card>
            <h2 className='sr-only'>Exports</h2>
            <AdminEditorPanel
              status={
                <>
                  {orgError ? (
                    <StatusBanner variant='error' title='Organization error'>
                      {orgError}
                    </StatusBanner>
                  ) : null}
                  {exportError ? (
                    <StatusBanner variant='error' title='Export error'>
                      {exportError}
                    </StatusBanner>
                  ) : null}
                  {exportWarnings.length > 0 ? (
                    <StatusBanner variant='info' title='Export warnings'>
                      {exportWarnings.length} warning(s) encountered. See file
                      for details.
                    </StatusBanner>
                  ) : null}
                </>
              }
              actions={
                <>
                  <Button
                    type='button'
                    onClick={() => {
                      void handleExport();
                    }}
                    disabled={isExportBusy}
                    loading={isExportBusy && exportTarget === 'all'}
                    loadingLabel='Exporting…'
                  >
                    Export all
                  </Button>
                  <Button
                    type='button'
                    variant='secondary'
                    onClick={() => {
                      if (selectedOrgName) {
                        void handleExport(selectedOrgName);
                      }
                    }}
                    disabled={isExportBusy || !selectedOrgName}
                    loading={isExportBusy && exportTarget === 'selected'}
                    loadingLabel='Exporting…'
                  >
                    Export selected
                  </Button>
                </>
              }
            >
              <p className='text-sm text-slate-600'>
                Download the current dataset as a JSON file.
              </p>
              <AdminFieldGrid columns={1}>
                <AdminField
                  label='Organization (optional)'
                  htmlFor='admin-export-org'
                >
                  <Select
                    id='admin-export-org'
                    value={selectedOrgName}
                    onChange={(event) => setSelectedOrgName(event.target.value)}
                    disabled={isOrgLoading}
                  >
                    <option value=''>All organizations</option>
                    {organizations.map((org) => (
                      <option key={org.id} value={org.name}>
                        {org.name}
                      </option>
                    ))}
                  </Select>
                </AdminField>
              </AdminFieldGrid>
            </AdminEditorPanel>
          </Card>
        </>
      )}
    </div>
  );
}
