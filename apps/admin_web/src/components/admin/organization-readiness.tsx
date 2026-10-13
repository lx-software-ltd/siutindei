'use client';

import { useEffect, useState } from 'react';
import { useQueryState } from 'nuqs';

import { ApiError } from '../../lib/api-client';
import { refreshCatalogHistory } from '../../lib/admin-query-client';
import {
  decideOrgReview,
  getOrgReviewDetail,
  type OrgReviewDetail,
  type OrgReviewIssue,
} from '../../lib/api-client-org-review';
import { StatusBanner } from '../status-banner';
import { AdminField, AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminInputCard } from '../ui/admin-input-card';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { Button } from '../ui/button';

function sectionForIssue(entityType: string) {
  if (entityType === 'location') {
    return 'locations';
  }
  if (entityType === 'activity') {
    return 'activities';
  }
  return 'organizations';
}

export function OrganizationReadiness({ orgId }: { orgId: string }) {
  const [, setSection] = useQueryState('section');
  const [, setOrg] = useQueryState('org');
  const [, setLocation] = useQueryState('location');
  const [, setActivity] = useQueryState('activity');
  const [, setTab] = useQueryState('tab');
  const [, setOrganization] = useQueryState('organization');
  const [detail, setDetail] = useState<OrgReviewDetail | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [force, setForce] = useState(false);
  const [activeAction, setActiveAction] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError('');
    getOrgReviewDetail(orgId)
      .then((row) => {
        if (!cancelled) {
          setDetail(row);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : 'Failed to load readiness.'
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [orgId, notice]);

  function openIssue(entry: OrgReviewIssue) {
    if (
      entry.code === 'activity_no_location' ||
      entry.code === 'no_locations' ||
      entry.code === 'missing_coordinates'
    ) {
      void setSection('data-quality');
      void setTab('locations');
      void setOrganization(orgId);
      return;
    }
    if (entry.code === 'name_needs_cleanup') {
      void setSection('data-quality');
      void setTab('names');
      void setOrganization(orgId);
      return;
    }
    if (entry.code === 'possible_duplicate') {
      void setSection('data-quality');
      void setTab(null);
      void setOrganization(orgId);
      return;
    }
    if (entry.code === 'pending_category' || entry.code === 'category_check_pending') {
      void setSection('data-quality');
      void setTab('checks');
      void setOrganization(orgId);
      void setOrg(orgId);
      return;
    }
    void setOrg(orgId);
    void setSection(sectionForIssue(entry.entity_type));
    if (entry.entity_type === 'location') {
      void setLocation(entry.entity_id);
      void setActivity(null);
      return;
    }
    if (entry.entity_type === 'activity') {
      void setActivity(entry.entity_id);
      void setLocation(null);
      return;
    }
    void setLocation(null);
    void setActivity(null);
  }

  async function decide(action: 'approve' | 'reject' | 'reopen') {
    setActiveAction(action);
    setError('');
    setNotice('');
    try {
      await decideOrgReview(orgId, {
        action,
        force: action === 'approve' ? force : undefined,
      });
      refreshCatalogHistory();
      setNotice(
        action === 'approve'
          ? 'Organization approved. Public search can stay cached for up to 5 minutes.'
          : `Organization ${action === 'reopen' ? 'reopened' : 'rejected'}.`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update review.');
    } finally {
      setActiveAction(null);
    }
  }

  const blockers = detail?.issues.filter((issue) => issue.severity === 'blocker') ?? [];

  return (
    <AdminInputCard
      title='Readiness'
      description='Imported, created, and suggested organizations stay in review until you release them. Public search keeps current listings until ORG_REVIEW_GATE_ENABLED is turned on.'
      status={
        <>
          {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
          {notice ? <StatusBanner kind='info'>{notice}</StatusBanner> : null}
        </>
      }
      actions={
        <>
          <Button
            type='button'
            onClick={() => void decide('approve')}
            disabled={activeAction !== null}
            loading={activeAction === 'approve'}
            loadingLabel='Saving…'
          >
            Approve
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void decide('reject')}
            disabled={activeAction !== null}
            loading={activeAction === 'reject'}
            loadingLabel='Saving…'
          >
            Reject
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void decide('reopen')}
            disabled={activeAction !== null}
            loading={activeAction === 'reopen'}
            loadingLabel='Saving…'
          >
            Reopen
          </Button>
        </>
      }
    >
      <AdminFieldGrid columns={1}>
          {!detail ? (
            <p className='text-sm text-slate-600'>Loading readiness…</p>
          ) : detail.issues.length === 0 ? (
            <AdminReadOnlyValue label='Issues'>Nothing is missing.</AdminReadOnlyValue>
          ) : (
            <ul className='col-span-full space-y-4'>
              {detail.issues.map((entry) => (
                <li key={`${entry.entity_id}-${entry.code}`}>
                  <AdminReadOnlyValue
                    label={entry.severity === 'blocker' ? 'Blocker' : 'Warning'}
                  >
                    <span>{entry.message}</span>{' '}
                    <button
                      type='button'
                      className='text-slate-900 underline'
                      onClick={() => openIssue(entry)}
                    >
                      Fix
                    </button>
                  </AdminReadOnlyValue>
                </li>
              ))}
            </ul>
          )}
          <AdminField>
            <label className='flex items-center gap-2 text-sm text-slate-700'>
              <input
                type='checkbox'
                checked={force}
                onChange={(event) => setForce(event.target.checked)}
              />
              Approve anyway{blockers.length > 0 ? ` (${blockers.length} missing)` : ''}
            </label>
          </AdminField>
      </AdminFieldGrid>
    </AdminInputCard>
  );
}
