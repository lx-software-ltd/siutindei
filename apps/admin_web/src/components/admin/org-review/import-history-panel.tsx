'use client';

import { useCallback, useEffect, useState } from 'react';
import { useQueryState } from 'nuqs';

import { ApiError } from '../../../lib/api-client';
import {
  listImportJobs,
  type ImportJobListItem,
} from '../../../lib/api-client-org-review';
import { Button } from '../../ui/button';
import { Card } from '../../ui/card';
import { DataTable } from '../../ui/data-table';
import { StatusBanner } from '../../status-banner';

export function ImportHistoryPanel() {
  const [, setTab] = useQueryState('tab');
  const [, setJob] = useQueryState('job');
  const [items, setItems] = useState<ImportJobListItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async (cursor?: string) => {
    setIsLoading(true);
    setError('');
    try {
      const response = await listImportJobs(cursor);
      setItems((prev) =>
        cursor ? [...prev, ...response.items] : response.items
      );
      setNextCursor(response.next_cursor ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load imports.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card
      title='Import history'
      description='Open the organizations written by a previous import.'
    >
      {error && (
        <div className='mb-4'>
          <StatusBanner variant='error' title='Import history'>
            {error}
          </StatusBanner>
        </div>
      )}
      {isLoading && items.length === 0 ? (
        <p className='text-sm text-slate-600'>Loading imports...</p>
      ) : (
        <DataTable
          columns={[
            {
              key: 'created',
              header: 'When',
              primary: true,
              render: (item: ImportJobListItem) =>
                item.created_at
                  ? new Date(item.created_at).toLocaleString()
                  : '—',
            },
            {
              key: 'file',
              header: 'File',
              secondary: true,
              render: (item: ImportJobListItem) => item.object_key,
            },
            {
              key: 'mode',
              header: 'Mode',
              render: (item: ImportJobListItem) =>
                item.dry_run ? 'Dry run' : item.status,
            },
            {
              key: 'orgs',
              header: 'Organizations',
              render: (item: ImportJobListItem) => {
                const counts = item.summary?.organizations;
                if (!counts) {
                  return '—';
                }
                return `created ${counts.created}, updated ${counts.updated}`;
              },
            },
          ]}
          data={items}
          keyExtractor={(item) => item.id}
          emptyMessage='No imports yet.'
          nextCursor={nextCursor}
          onLoadMore={() => {
            if (nextCursor) {
              void load(nextCursor);
            }
          }}
          isLoading={isLoading}
          renderActions={(item) =>
            item.dry_run ? null : (
              <Button
                type='button'
                size='sm'
                variant='secondary'
                onClick={() => {
                  void setJob(item.id);
                  void setTab('review');
                }}
              >
                View orgs
              </Button>
            )
          }
        />
      )}
    </Card>
  );
}
