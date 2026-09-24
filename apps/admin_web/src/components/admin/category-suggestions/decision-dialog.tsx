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
import { Button } from '../../ui/button';
import { Card } from '../../ui/card';
import { CascadingCategorySelect } from '../../ui/cascading-category-select';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { LanguageToggleInput } from '../../ui/language-toggle-input';

interface DecisionDialogProps {
  suggestion: CategorySuggestion;
  onDecided: (next: CategorySuggestion) => void;
  onError: (message: string) => void;
}

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
  const [isSaving, setIsSaving] = useState(false);

  async function submit(action: 'approve' | 'map' | 'reject') {
    setIsSaving(true);
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
      setIsSaving(false);
    }
  }

  const nameValues = {
    en: name,
    zh: translations.zh,
    yue: translations.yue,
  };

  return (
    <Card title='Decision' description='Approve a new category, map to one, or reject.'>
      <div className='space-y-4'>
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
        <CascadingCategorySelect
          tree={tree}
          value={parentId}
          onChange={(categoryId) => setParentId(categoryId)}
        />
        <div className='space-y-1'>
          <Label htmlFor='suggestion-map-target'>Map or reject target</Label>
          <Input
            id='suggestion-map-target'
            value={mapId}
            placeholder='Existing category id'
            onChange={(event) => setMapId(event.target.value)}
          />
          <CascadingCategorySelect
            tree={tree}
            value={mapId}
            onChange={(categoryId) => setMapId(categoryId)}
          />
        </div>
        <div className='space-y-1'>
          <Label htmlFor='suggestion-notes'>Notes</Label>
          <Input
            id='suggestion-notes'
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>
        <div className='flex flex-wrap gap-3'>
          <Button type='button' onClick={() => void submit('approve')} disabled={isSaving}>
            Approve
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void submit('map')}
            disabled={isSaving || !mapId}
          >
            Map
          </Button>
          <Button
            type='button'
            variant='secondary'
            onClick={() => void submit('reject')}
            disabled={isSaving}
          >
            Reject
          </Button>
        </div>
      </div>
    </Card>
  );
}
