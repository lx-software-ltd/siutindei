'use client';

import { useEffect, useState } from 'react';

import {
  enrichCategorySuggestion,
  getCategorySuggestion,
  type CategorySuggestion,
} from '../../../lib/api-client-category-suggestions';
import { Button } from '../../ui/button';
import { Card } from '../../ui/card';
import { DecisionDialog } from './decision-dialog';

interface SuggestionDetailProps {
  suggestionId: string;
  onClose: () => void;
}

export function SuggestionDetail({ suggestionId, onClose }: SuggestionDetailProps) {
  const [item, setItem] = useState<CategorySuggestion | null>(null);
  const [error, setError] = useState('');

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
    setError('');
    try {
      await enrichCategorySuggestion(suggestionId);
      const row = await getCategorySuggestion(suggestionId);
      setItem(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Enrich failed.');
    }
  }

  if (!item) {
    return (
      <Card title='Suggestion' description='Loading suggestion.'>
        {error ? <p className='text-sm text-red-600'>{error}</p> : null}
      </Card>
    );
  }

  return (
    <div className='space-y-4'>
      <Card
        title={item.requested_name}
        description={item.rationale || 'No rationale yet.'}
      >
        {error ? <p className='mb-3 text-sm text-red-600'>{error}</p> : null}
        {item.status === 'rejected' && !item.merged_into_category_id ? (
          <p className='mb-3 text-sm text-amber-800'>
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
        <ul className='mt-4 space-y-1 text-sm text-slate-700'>
          {(item.activities || []).map((link) => (
            <li key={link.activity_id}>
              {link.org_name || link.org_id}: {link.activity_name || link.requested_name}
            </li>
          ))}
        </ul>
        <div className='mt-4 flex flex-wrap gap-3'>
          <Button type='button' variant='secondary' onClick={() => void enrich()}>
            Enrich again
          </Button>
          <Button type='button' variant='secondary' onClick={onClose}>
            Close
          </Button>
        </div>
      </Card>
      <DecisionDialog
        suggestion={item}
        onDecided={setItem}
        onError={setError}
      />
    </div>
  );
}
