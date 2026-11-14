'use client';

import { useEffect, useState } from 'react';

import { ApiError } from '../../../lib/api-client';
import { getOrgReviewSummary, type AreaReadiness } from '../../../lib/api-client-org-review';
import { AdminInlineError } from '../../ui/admin-inline-error';
import { AdminInputCard } from '../../ui/admin-input-card';
import { AdminReadOnlyValue } from '../../ui/admin-read-only-value';
import { StatusBadge } from '../../ui/status-badge';

const KIND_LABELS: ReadonlyArray<[string, string]> = [
  ['class', 'Classes'],
  ['camp', 'Camps'],
  ['place', 'Places'],
  ['preschool', 'Nurseries'],
  ['eat', 'Eat'],
];

function percent(share: number | null): string {
  return share === null ? '—' : `${Math.round(share * 100)}%`;
}

function shareLine(part: number, whole: number, share: number | null, need: number): string {
  return `${part} of ${whole} (${percent(share)}); needs ${percent(need)}`;
}

export interface AreaReadinessCardProps {
  areaId: string;
  areaName: string;
  /** Changes after a bulk action so the shares reload. */
  refreshKey?: unknown;
}

/** The opening gate for the neighbourhood chosen on Catalog. */
export function AreaReadinessCard({ areaId, areaName, refreshKey }: AreaReadinessCardProps) {
  const [loaded, setLoaded] = useState<{ areaId: string; readiness: AreaReadiness | null }>();
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getOrgReviewSummary(areaId)
      .then((summary) => {
        if (!cancelled) {
          setLoaded({ areaId, readiness: summary.readiness ?? null });
          setError('');
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load readiness.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [areaId, refreshKey]);

  const readiness = loaded?.areaId === areaId ? loaded.readiness : null;
  return (
    <AdminInputCard
      title='Ready to open?'
      titleLevel='h3'
      description={areaName}
      titleAccessory={
        readiness ? (
          <StatusBadge
            status={readiness.ready ? 'done' : 'pending'}
            label={readiness.ready ? 'Ready' : 'Not yet'}
          />
        ) : null
      }
      data-testid='area-readiness-card'
    >
      {error ? <AdminInlineError>{error}</AdminInlineError> : null}
      {readiness ? (
        <div className='grid gap-4 sm:grid-cols-3'>
          <AdminReadOnlyValue label='Classes and camps complete'>
            {shareLine(
              readiness.complete_classes_and_camps,
              readiness.classes_and_camps,
              readiness.complete_share,
              readiness.thresholds.complete_share
            )}
          </AdminReadOnlyValue>
          <AdminReadOnlyValue label='Organisers parent-checked'>
            {shareLine(
              readiness.verified_organisers,
              readiness.organisers,
              readiness.verified_share,
              readiness.thresholds.verified_share
            )}
          </AdminReadOnlyValue>
          <AdminReadOnlyValue label='Listings'>
            {KIND_LABELS.map(([kind, label]) => `${label} ${readiness.listings_by_kind[kind] ?? 0}`).join(
              ' · '
            )}
          </AdminReadOnlyValue>
        </div>
      ) : error ? null : (
        <p className='text-sm text-ink-500'>Loading…</p>
      )}
    </AdminInputCard>
  );
}
