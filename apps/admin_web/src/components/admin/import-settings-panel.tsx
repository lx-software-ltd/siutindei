'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { adminTabLabel, formatAdminPageName } from '../../lib/admin-page-name';
import { getAdminQueryClient } from '../../lib/admin-query-client';
import { adminQueryKeys } from '../../lib/admin-query-keys';
import { ApiError } from '../../lib/api-client';
import {
  getImportSettings,
  updateImportSettings,
  type ImportSettings,
} from '../../lib/api-client-imports';
import { StatusBanner } from '../status-banner';
import { AdminField, AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminInputCard } from '../ui/admin-input-card';
import { Button } from '../ui/button';
import { Select } from '../ui/select';

const PAGE_NAME = formatAdminPageName('Imports', adminTabLabel.settings);

const EMPTY_SETTINGS: ImportSettings = {
  skip_deleted_organizations: true,
  name_cleanup: 'apply',
  unknown_categories: 'capture',
  duplicates: 'off',
  locations: 'off',
  categories: 'off',
  updated_at: null,
};

export function ImportSettingsPanel() {
  const settingsQuery = useQuery({
    queryKey: adminQueryKeys.importSettings(),
    queryFn: getImportSettings,
  });
  const [draft, setDraft] = useState<ImportSettings | null>(null);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  const settings = draft ?? settingsQuery.data ?? EMPTY_SETTINGS;

  useEffect(() => {
    if (settingsQuery.data && draft === null) {
      setDraft(settingsQuery.data);
    }
  }, [draft, settingsQuery.data]);

  function update<K extends keyof ImportSettings>(key: K, value: ImportSettings[K]) {
    setNotice('');
    setConflict(false);
    setError('');
    setDraft({ ...settings, [key]: value });
  }

  async function save() {
    setSaving(true);
    setError('');
    setConflict(false);
    setNotice('');
    try {
      const updated = await updateImportSettings(settings);
      setDraft(updated);
      setNotice('Settings saved.');
      await getAdminQueryClient().invalidateQueries({
        queryKey: adminQueryKeys.importSettings(),
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict(true);
        setDraft(null);
        await settingsQuery.refetch();
      } else {
        setError(
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Save failed.'
        );
      }
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
            {conflict ? (
              <StatusBanner kind='error'>
                Settings were updated. Review the current values and save again.
              </StatusBanner>
            ) : null}
            {error || loadError ? (
              <StatusBanner kind='error'>{error || loadError}</StatusBanner>
            ) : null}
            {notice ? <StatusBanner kind='saved'>{notice}</StatusBanner> : null}
            {!settings.skip_deleted_organizations ? (
              <StatusBanner kind='info'>
                Deleted organizations can be created again by a later import.
              </StatusBanner>
            ) : null}
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
        <section className='space-y-2'>
          <h4 className='text-sm font-semibold text-slate-900'>Matching</h4>
          <p className='text-sm text-slate-600'>
            An import matches a place id, then a source id, then the same
            manager and name, then a cleaned name. Merges are always followed.
            Catalog version 1 is protected.
          </p>
        </section>
        <section className='space-y-3'>
          <h4 className='text-sm font-semibold text-slate-900'>While writing</h4>
          <AdminFieldGrid columns={1}>
            <AdminField span='full'>
              <label className='flex items-center gap-2 text-sm text-slate-700'>
                <input
                  type='checkbox'
                  checked={settings.skip_deleted_organizations}
                  onChange={(event) =>
                    update('skip_deleted_organizations', event.target.checked)
                  }
                />
                Skip deleted organizations
              </label>
            </AdminField>
            <AdminField label='Names' htmlFor='import-name-cleanup'>
              <Select
                id='import-name-cleanup'
                value={settings.name_cleanup}
                onChange={(event) =>
                  update(
                    'name_cleanup',
                    event.target.value as ImportSettings['name_cleanup']
                  )
                }
              >
                <option value='apply'>Apply</option>
                <option value='propose'>Propose</option>
                <option value='off'>Off</option>
              </Select>
            </AdminField>
            <AdminField label='Unknown categories' htmlFor='import-unknown-categories'>
              <Select
                id='import-unknown-categories'
                value={settings.unknown_categories}
                onChange={(event) =>
                  update(
                    'unknown_categories',
                    event.target.value as ImportSettings['unknown_categories']
                  )
                }
              >
                <option value='capture'>Capture</option>
                <option value='fail'>Fail</option>
              </Select>
            </AdminField>
          </AdminFieldGrid>
        </section>
        <section className='space-y-3'>
          <h4 className='text-sm font-semibold text-slate-900'>After import</h4>
          <p className='text-sm text-slate-600'>
            These checks run on the organizations and activities this import
            created or updated, and after an enrichment apply. Duplicates
            then cover that organization. Locations run when a venue or
            activity was saved, and categories run when an activity was
            saved. A dry-run does not start them.
          </p>
          <AdminFieldGrid columns={1}>
            <AdminField label='Duplicates' htmlFor='import-duplicates'>
              <Select
                id='import-duplicates'
                value={settings.duplicates}
                onChange={(event) =>
                  update(
                    'duplicates',
                    event.target.value as ImportSettings['duplicates']
                  )
                }
              >
                <option value='off'>Off</option>
                <option value='report'>Report</option>
              </Select>
            </AdminField>
            <AdminField label='Locations' htmlFor='import-locations'>
              <Select
                id='import-locations'
                value={settings.locations}
                onChange={(event) =>
                  update('locations', event.target.value as ImportSettings['locations'])
                }
              >
                <option value='off'>Off</option>
                <option value='check'>Check</option>
              </Select>
            </AdminField>
            <AdminField label='Categories' htmlFor='import-categories'>
              <Select
                id='import-categories'
                value={settings.categories}
                onChange={(event) =>
                  update(
                    'categories',
                    event.target.value as ImportSettings['categories']
                  )
                }
              >
                <option value='off'>Off</option>
                <option value='check'>Check</option>
              </Select>
            </AdminField>
          </AdminFieldGrid>
        </section>
      </AdminInputCard>
    </>
  );
}
