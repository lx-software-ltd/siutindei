'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { adminTabLabel, formatAdminPageName } from '../../lib/admin-page-name';
import { getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import { ApiError } from '../../lib/api-client';
import {
  getImportDataQualitySettings,
  updateImportDataQualitySettings,
  type ImportDataQualitySettings,
} from '../../lib/api-client-imports';
import { StatusBanner } from '../status-banner';
import { AdminField, AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminInputCard } from '../ui/admin-input-card';
import { Button } from '../ui/button';

const PAGE_NAME = formatAdminPageName('Imports', adminTabLabel.settings);

const QUALITY_OPTIONS: {
  key: keyof ImportDataQualitySettings;
  label: string;
}[] = [
  { key: 'duplicates', label: adminTabLabel.duplicates },
  { key: 'names', label: adminTabLabel.names },
  { key: 'locations', label: adminTabLabel.locations },
  { key: 'categories', label: adminTabLabel.categories },
];

const OFF_SETTINGS: ImportDataQualitySettings = {
  duplicates: false,
  names: false,
  locations: false,
  categories: false,
};

export function ImportSettingsPanel() {
  const settingsQuery = useQuery({
    queryKey: adminQueryKeys.importSettings(),
    queryFn: getImportDataQualitySettings,
  });
  const [draft, setDraft] = useState<ImportDataQualitySettings | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const settings = draft ?? settingsQuery.data ?? OFF_SETTINGS;

  useEffect(() => {
    if (settingsQuery.data && draft === null) {
      setDraft(settingsQuery.data);
    }
  }, [draft, settingsQuery.data]);

  async function save() {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const updated = await updateImportDataQualitySettings(settings);
      setDraft(updated);
      setNotice('Settings saved.');
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.importSettings(),
      });
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Save failed.'
      );
    } finally {
      setSaving(false);
    }
  }

  const loadError =
    settingsQuery.isError && !draft
      ? settingsQuery.error instanceof Error
        ? settingsQuery.error.message
        : 'Failed to load settings'
      : '';

  return (
    <>
      <h2 className='sr-only'>{PAGE_NAME}</h2>
      <AdminInputCard
        title={adminTabLabel.settings}
        titleLevel='h3'
        status={
          <>
            {error || loadError ? (
              <StatusBanner kind='error'>{error || loadError}</StatusBanner>
            ) : null}
            {notice ? <StatusBanner kind='saved'>{notice}</StatusBanner> : null}
          </>
        }
        actions={
          <Button
            type='button'
            onClick={() => {
              void save();
            }}
            loading={saving}
            disabled={settingsQuery.isLoading && !draft}
          >
            Save settings
          </Button>
        }
      >
        <p className='text-sm text-slate-600'>
          Tick the Data quality checks that run after a live import. Sweeps
          use pending review. A dry-run does not start them.
        </p>
        <AdminFieldGrid columns={1}>
          <AdminField span='full'>
            <div className='space-y-2'>
              {QUALITY_OPTIONS.map((option) => (
                <label
                  key={option.key}
                  className='flex items-center gap-2 text-sm text-slate-700'
                >
                  <input
                    type='checkbox'
                    checked={settings[option.key]}
                    onChange={(event) => {
                      setNotice('');
                      setDraft({
                        ...settings,
                        [option.key]: event.target.checked,
                      });
                    }}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </AdminField>
        </AdminFieldGrid>
      </AdminInputCard>
    </>
  );
}
