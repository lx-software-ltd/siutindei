'use client';

import { useEffect, useState } from 'react';

import { getAdminQueryClient } from '../../../lib/admin-query-client';
import {
  mergeOrganizations,
  type OrgDuplicateMember,
  type OrgMergeResult,
} from '../../../lib/api-client-data-quality';
import { ApiError } from '../../../lib/api-client';
import { Button } from '../../ui/button';
import { StatusBanner } from '../../status-banner';

interface OrganizationMergeEditorProps {
  organizations: OrgDuplicateMember[];
  suggestedSurvivorId?: string;
  onMerged: () => void;
}

function invalidateCatalog() {
  void getAdminQueryClient().invalidateQueries({ queryKey: ['admin'] });
}

export function OrganizationMergeEditor({
  organizations,
  suggestedSurvivorId,
  onMerged,
}: OrganizationMergeEditorProps) {
  const [survivorId, setSurvivorId] = useState(
    suggestedSurvivorId || organizations[0]?.id || ''
  );
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<OrgMergeResult | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMerging, setIsMerging] = useState(false);

  useEffect(() => {
    setSurvivorId(suggestedSurvivorId || organizations[0]?.id || '');
    setOverrides({});
  }, [suggestedSurvivorId, organizations]);

  useEffect(() => {
    const sources = organizations.filter((org) => org.id !== survivorId);
    if (!survivorId || sources.length === 0) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError('');
    mergeOrganizations({
      survivor_id: survivorId,
      source_ids: sources.map((org) => org.id),
      dry_run: true,
      field_overrides: overrides,
    })
      .then((result) => {
        if (!cancelled) {
          setPreview(result);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Preview failed.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [organizations, survivorId, overrides]);

  async function confirmMerge() {
    if (!preview) {
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
      onMerged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Merge failed.');
    } finally {
      setIsMerging(false);
    }
  }

  return (
    <div className='space-y-3'>
      {error ? (
        <StatusBanner variant='error' title='Merge'>
          {error}
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
      {isLoading ? <p className='text-sm text-slate-600'>Preparing preview...</p> : null}
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
          activities. Pricing and schedules stay on those activities.
        </p>
      ) : null}
      <Button
        type='button'
        onClick={() => void confirmMerge()}
        disabled={!preview || isLoading}
        loading={isMerging}
        loadingLabel='Merging…'
      >
        Merge
      </Button>
    </div>
  );
}
