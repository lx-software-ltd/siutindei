'use client';

import { useState } from 'react';

import { useActivityCategories } from '../../../hooks/use-activity-categories';
import { decideCategorySuggestion } from '../../../lib/api-client-category-suggestions';
import type { CategorySuggestion } from '../../../lib/api-client-category-suggestions';
import {
  buildTranslationsPayload,
  extractTranslations,
  type LanguageCode,
} from '../../../lib/translations';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { Button } from '../../ui/button';
import { CascadingCategorySelect } from '../../ui/cascading-category-select';
import { Input } from '../../ui/input';
import { LanguageToggleInput } from '../../ui/language-toggle-input';

interface DecisionDialogProps {
  suggestion: CategorySuggestion;
  onDecided: (next: CategorySuggestion) => void;
  onError: (message: string) => void;
}

type DecisionAction = 'approve' | 'map' | 'reject';

export function DecisionDialog({
  suggestion,
  onDecided,
  onError,
}: DecisionDialogProps) {
  const { tree } = useActivityCategories();
  const [name, setName] = useState(
    suggestion.suggested_name || suggestion.requested_name
  );
  const [translations, setTranslations] = useState(
    extractTranslations(suggestion.name_translations)
  );
  const [parentId, setParentId] = useState(suggestion.suggested_parent_id || '');
  const [mapId, setMapId] = useState(suggestion.maps_to_category_id || '');
  const [notes, setNotes] = useState('');
  const [pending, setPending] = useState<DecisionAction | null>(null);

  async function submit(action: DecisionAction) {
    setPending(action);
    try {
      const body: Record<string, unknown> = { action, notes };
      if (action === 'approve') {
        body.name = name.trim();
        body.name_translations = buildTranslationsPayload(translations);
        body.parent_id = parentId || null;
        body.display_order =
          suggestion.alternatives?.display_order_hint ?? 0;
      }
      if (action === 'map' || (action === 'reject' && mapId)) {
        body.category_id = mapId;
      }
      onDecided(await decideCategorySuggestion(suggestion.id, body));
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Decision failed.');
    } finally {
      setPending(null);
    }
  }

  const nameValues = {
    en: name,
    zh: translations.zh,
    yue: translations.yue,
  };
  const isSaving = pending !== null;

  return (
    <AdminEditorPanel
      actions={
        <>
          <Button
            type='button'
            onClick={() => void submit('approve')}
            disabled={isSaving}
            loading={pending === 'approve'}
            loadingLabel='Saving…'
          >
            Approve
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void submit('map')}
            disabled={isSaving || !mapId}
            loading={pending === 'map'}
            loadingLabel='Saving…'
          >
            Map
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void submit('reject')}
            disabled={isSaving}
            loading={pending === 'reject'}
            loadingLabel='Saving…'
          >
            Reject
          </Button>
        </>
      }
    >
      <p className='text-sm text-slate-600'>
        Approve a new category, map to one, or reject.
      </p>
      <AdminFieldGrid columns={1}>
        <AdminField span='full'>
          <LanguageToggleInput
            id='suggestion-decision-name'
            label='Category name'
            values={nameValues}
            onChange={(language: LanguageCode, value: string) => {
              if (language === 'en') {
                setName(value);
                return;
              }
              setTranslations({ ...translations, [language]: value });
            }}
          />
        </AdminField>
        <AdminField span='full'>
          <CascadingCategorySelect
            tree={tree}
            value={parentId}
            onChange={(categoryId) => setParentId(categoryId)}
          />
        </AdminField>
        <AdminField label='Map or reject target' htmlFor='suggestion-map-target'>
          <Input
            id='suggestion-map-target'
            value={mapId}
            placeholder='Existing category id'
            onChange={(event) => setMapId(event.target.value)}
          />
          <div className='mt-2'>
            <CascadingCategorySelect
              tree={tree}
              value={mapId}
              onChange={(categoryId) => setMapId(categoryId)}
            />
          </div>
        </AdminField>
        <AdminField label='Notes' htmlFor='suggestion-notes'>
          <Input
            id='suggestion-notes'
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </AdminField>
      </AdminFieldGrid>
      {!mapId ? (
        <p className='text-sm text-slate-600'>
          Reject without a target leaves these activities in Pending
          categorisation. Organization review stays blocked until you map
          them.
        </p>
      ) : null}
    </AdminEditorPanel>
  );
}
