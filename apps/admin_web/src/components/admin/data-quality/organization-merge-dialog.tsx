'use client';

import { useState } from 'react';

import { ApiError } from '../../../lib/api-client';
import {
  searchOrganizationsForMerge,
  type OrgDuplicateMember,
} from '../../../lib/api-client-data-quality';
import { AdminDialog } from '../../ui/admin-dialog';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { OrganizationMergeEditor } from './organization-merge-editor';

interface OrganizationMergeDialogProps {
  anchor: { id: string; name: string } | null;
  onClose: () => void;
  onMerged?: (survivorId: string) => void;
}

export function OrganizationMergeDialog({
  anchor,
  onClose,
  onMerged,
}: OrganizationMergeDialogProps) {
  return (
    <AdminDialog
      open={anchor !== null}
      title='Merge organization'
      description='Choose the other organization. Blank fields are filled from it. You choose the name when they differ.'
      onClose={onClose}
      contentClassName='w-full max-w-lg'
      footer={null}
    >
      {anchor ? (
        <MergeSearch
          key={anchor.id}
          anchor={anchor}
          onClose={onClose}
          onMerged={onMerged}
        />
      ) : null}
    </AdminDialog>
  );
}

function MergeSearch({
  anchor,
  onClose,
  onMerged,
}: {
  anchor: { id: string; name: string };
  onClose: () => void;
  onMerged?: (survivorId: string) => void;
}) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<OrgDuplicateMember[]>([]);
  const [partner, setPartner] = useState<OrgDuplicateMember | null>(null);
  const [error, setError] = useState('');

  async function search() {
    setError('');
    try {
      const page = await searchOrganizationsForMerge(query.trim());
      setMatches(page.items.filter((item) => item.id !== anchor.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Search failed.');
    }
  }

  const organizations: OrgDuplicateMember[] = partner
    ? [
        {
          id: anchor.id,
          name: anchor.name,
          review_status: 'pending_review',
          status: 'operational',
        },
        partner,
      ]
    : [];

  return (
    <>
      {error ? <p className='mb-3 text-sm text-red-700'>{error}</p> : null}
      {partner === null ? (
        <div className='space-y-3'>
          <div className='flex gap-2'>
            <Input
              aria-label='Find organization'
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Button type='button' variant='secondary' onClick={() => void search()}>
              Find
            </Button>
          </div>
          <ul className='space-y-2'>
            {matches.map((item) => (
              <li key={item.id}>
                <button
                  type='button'
                  className='text-sm text-slate-900 underline'
                  onClick={() => setPartner(item)}
                >
                  {item.name}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <OrganizationMergeEditor
          key={`${organizations.map((org) => org.id).join(',')}:${anchor.id}`}
          organizations={organizations}
          suggestedSurvivorId={anchor.id}
          onMerged={(survivorId) => {
            onMerged?.(survivorId);
            onClose();
          }}
        />
      )}
    </>
  );
}
