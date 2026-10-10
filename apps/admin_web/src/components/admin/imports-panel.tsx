'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQueryState } from 'nuqs';

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
import { Input } from '../ui/input';
import { StatusBanner } from '../status-banner';
import { ImportHistoryPanel } from './org-review/import-history-panel';

type ImportTab = 'import' | 'history';
type ImportStatus = 'idle' | 'uploading' | 'processing' | 'done' | 'error';
type ExportStatus = 'idle' | 'loading' | 'done' | 'error';
type ExportTarget = 'all' | 'selected';

const IMPORT_TABS: { key: ImportTab; label: string }[] = [
  { key: 'import', label: 'Import' },
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
  const [, setSection] = useQueryState('section');
  const [, setJobParam] = useQueryState('job');
  const activeTab: ImportTab = tabParam === 'history' ? 'history' : 'import';

  useEffect(() => {
    if (tabParam !== 'review') {
      return;
    }
    void setSection('catalog');
    void setTabParam(null);
  }, [setSection, setTabParam, tabParam]);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [skipExisting, setSkipExisting] = useState(true);
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
        allow_updates: !skipExisting,
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
    <div className='space-y-4'>
      <AdminTabStrip
        aria-label='Imports'
        items={IMPORT_TABS}
        activeKey={activeTab}
        onChange={(key) => {
          void setTabParam(key === 'import' ? null : key);
        }}
      />
      {activeTab === 'history' && <ImportHistoryPanel />}
      {activeTab === 'import' && (
        <>
          <Card>
            <h2 className='sr-only'>Imports</h2>
            <AdminEditorPanel
              status={
                importError ? (
                  <StatusBanner kind='error'>
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
                <AdminField span='full'>
                  <label className='flex items-center gap-2 text-sm text-slate-700'>
                    <input
                      id='admin-import-skip-existing'
                      type='checkbox'
                      checked={skipExisting}
                      onChange={(event) => setSkipExisting(event.target.checked)}
                    />
                    Skip records that already exist
                  </label>
                  <p className='mt-1 text-sm text-slate-600'>
                    Existing organizations, venues, and activities stay
                    unchanged. New rows are still added, including a new
                    venue on an organization that already exists.
                  </p>
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
                      void setTabParam(null);
                      void setSection('catalog');
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
                  {exportError ? (
                    <StatusBanner kind='error'>
                      {exportError}
                    </StatusBanner>
                  ) : null}
                  {exportWarnings.length > 0 ? (
                    <StatusBanner kind='info'>
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
                  <Input
                    id='admin-export-org'
                    value={selectedOrgName}
                    aria-label='Organization name'
                    placeholder='Leave blank to export every organization'
                    onChange={(event) => setSelectedOrgName(event.target.value)}
                  />
                </AdminField>
              </AdminFieldGrid>
            </AdminEditorPanel>
          </Card>
        </>
      )}
    </div>
  );
}
