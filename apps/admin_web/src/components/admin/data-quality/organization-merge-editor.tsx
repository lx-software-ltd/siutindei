'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { getAdminQueryClient } from '../../../lib/admin-query-client';
import {
  mergeOrganizations,
  type OrgDuplicateMember,
} from '../../../lib/api-client-data-quality';
import { ApiError } from '../../../lib/api-client';
import { useConfirmDialog } from '../../../hooks/use-confirm-dialog';
import { Button } from '../../ui/button';
import { StatusBanner } from '../../status-banner';

interface OrganizationMergeEditorProps {
  organizations: OrgDuplicateMember[];
  suggestedSurvivorId?: string;
  onMerged: (survivorId: string) => void;
}

function invalidateCatalog() {
  void getAdminQueryClient().invalidateQueries({ queryKey: ['admin'] });
}

export function OrganizationMergeEditor({
  organizations,
  suggestedSurvivorId,
  onMerged,
}: OrganizationMergeEditorProps) {
  const { confirm, confirmDialog } = useConfirmDialog();
  const [survivorId, setSurvivorId] = useState(
    suggestedSurvivorId || organizations[0]?.id || ''
  );
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [isMerging, setIsMerging] = useState(false);
  const sources = organizations.filter((org) => org.id !== survivorId);
  const sourceKey = sources.map((org) => org.id).join(',');
  const overrideKey = JSON.stringify(overrides);
  const previewQuery = useQuery({
    queryKey: ['admin', 'org-merge-preview', survivorId, sourceKey, overrideKey],
    enabled: Boolean(survivorId) && sources.length > 0,
    queryFn: () =>
      mergeOrganizations({
        survivor_id: survivorId,
        source_ids: sources.map((org) => org.id),
        dry_run: true,
        field_overrides: overrides,
      }),
  });
  const preview = previewQuery.data ?? null;
  const previewError =
    previewQuery.error instanceof ApiError
      ? previewQuery.error.message
      : previewQuery.error
        ? 'Preview failed.'
        : '';

  async function confirmMerge() {
    if (!preview) {
      return;
    }
    const accepted = await confirm(
      'Merge organizations',
      'The other organizations are deleted. Matching addresses and activity names are combined.',
      { confirmLabel: 'Merge organizations', variant: 'danger' }
    );
    if (!accepted) {
      return;
    }
    setIsMerging(true);
    setError('');
    try {
      await mergeOrganizations({
        survivor_id: preview.survivor_id,
        source_ids: preview.source_ids,
        field_overrides: overrides,
      });
      invalidateCatalog();
      onMerged(preview.survivor_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Merge failed.');
    } finally {
      setIsMerging(false);
    }
  }

  return (
    <div className='space-y-3'>
      {confirmDialog}
      {error || previewError ? (
        <StatusBanner kind='error'>
          {error || previewError}
        </StatusBanner>
      ) : null}
      <fieldset className='space-y-2'>
        <legend className='text-sm font-medium text-slate-800'>Keep</legend>
        {organizations.map((org) => (
          <label key={org.id} className='flex items-center gap-2 text-sm text-slate-700'>
            <input
              type='radio'
              name='merge-survivor'
              checked={survivorId === org.id}
              onChange={() => {
                setOverrides({});
                setSurvivorId(org.id);
              }}
            />
            <span>{org.name}</span>
            <span className='text-slate-500'>{org.review_status.replaceAll('_', ' ')}</span>
          </label>
        ))}
      </fieldset>
      {previewQuery.isLoading ? <p className='text-sm text-slate-600'>Preparing preview...</p> : null}
      {preview?.warnings.map((warning) => (
        <p key={warning} className='text-sm text-amber-800'>
          {warning}
        </p>
      ))}
      {preview ? (
        <ul className='space-y-2 text-sm text-slate-700'>
          {preview.fields
            .filter((field) => field.conflict || field.result)
            .map((field) => (
              <li key={field.field}>
                <span className='font-medium'>{field.label}: </span>
                {field.conflict ? (
                  <span className='mt-1 flex flex-col gap-1'>
                    {[field.survivor_value, ...field.source_values.map((item) => item.value)]
                      .filter((value): value is string => Boolean(value))
                      .filter((value, index, all) => all.indexOf(value) === index)
                      .map((value) => (
                        <label key={value} className='flex items-center gap-2'>
                          <input
                            type='radio'
                            name={`merge-${field.field}`}
                            checked={(overrides[field.field] ?? field.result ?? '') === value}
                            onChange={() =>
                              setOverrides((current) => ({
                                ...current,
                                [field.field]: value,
                              }))
                            }
                          />
                          {value}
                        </label>
                      ))}
                  </span>
                ) : (
                  <span>{field.result}</span>
                )}
              </li>
            ))}
        </ul>
      ) : null}
      {preview ? (
        <p className='text-sm text-slate-600'>
          Moves {preview.moved.locations ?? 0} locations and {preview.moved.activities ?? 0}{' '}
          activities. Matching addresses and activity names are combined.
        </p>
      ) : null}
      <Button
        type='button'
        onClick={() => void confirmMerge()}
        disabled={!preview || previewQuery.isFetching}
        loading={isMerging}
        loadingLabel='Merging…'
      >
        Merge
      </Button>
    </div>
  );
}
