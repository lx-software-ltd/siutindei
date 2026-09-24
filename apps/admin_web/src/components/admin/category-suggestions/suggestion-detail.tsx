'use client';

import { useEffect, useState } from 'react';

import {
  enrichCategorySuggestion,
  getCategorySuggestion,
  type CategorySuggestion,
} from '../../../lib/api-client-category-suggestions';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { Button } from '../../ui/button';
import { DecisionDialog } from './decision-dialog';

interface SuggestionDetailProps {
  suggestionId: string;
  onClose: () => void;
  onReload?: () => void;
}

export function SuggestionDetail({
  suggestionId,
  onClose,
  onReload,
}: SuggestionDetailProps) {
  const [item, setItem] = useState<CategorySuggestion | null>(null);
  const [error, setError] = useState('');
  const [isEnriching, setIsEnriching] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCategorySuggestion(suggestionId)
      .then((row) => {
        if (!cancelled) {
          setItem(row);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [suggestionId]);

  async function enrich() {
    setIsEnriching(true);
    setError('');
    try {
      await enrichCategorySuggestion(suggestionId);
      const row = await getCategorySuggestion(suggestionId);
      setItem(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Enrich failed.');
    } finally {
      setIsEnriching(false);
    }
  }

  if (!item) {
    return (
      <AdminEditorPanel>
        <p className='text-sm text-slate-600'>Loading suggestion.</p>
        {error ? <p className='text-sm text-red-600'>{error}</p> : null}
      </AdminEditorPanel>
    );
  }

  return (
    <div className='space-y-4'>
      <AdminEditorPanel
        actions={
          <>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void enrich()}
              disabled={isEnriching}
              loading={isEnriching}
              loadingLabel='Enriching…'
            >
              Enrich again
            </Button>
            <Button type='button' variant='secondary' onClick={onClose}>
              Close
            </Button>
          </>
        }
      >
        {error ? <p className='text-sm text-red-600'>{error}</p> : null}
        <p className='text-sm text-slate-600'>
          {item.rationale || 'No rationale yet.'}
        </p>
        {item.status === 'rejected' && !item.merged_into_category_id ? (
          <p className='text-sm text-amber-800'>
            These activities are still in Pending categorisation, so the
            organization cannot be approved until you map them.
          </p>
        ) : null}
        <dl className='grid gap-2 text-sm md:grid-cols-2'>
          <div>Status: {item.status}</div>
          <div>Enrichment: {item.enrichment_status}</div>
          <div>Suggested: {item.suggested_name || '—'}</div>
          <div>Chinese: {item.name_translations?.zh || '—'}</div>
          <div>Confidence: {item.confidence ?? '—'}</div>
          <div>Activities: {item.activity_count}</div>
        </dl>
        <ul className='space-y-1 text-sm text-slate-700'>
          {(item.activities || []).map((link) => (
            <li key={link.activity_id}>
              {link.org_name || link.org_id}: {link.activity_name || link.requested_name}
            </li>
          ))}
        </ul>
      </AdminEditorPanel>
      <DecisionDialog
        suggestion={item}
        onDecided={(next) => {
          setItem(next);
          onReload?.();
        }}
        onError={setError}
      />
    </div>
  );
}
