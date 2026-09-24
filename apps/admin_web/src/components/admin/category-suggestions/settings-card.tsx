'use client';

import { useEffect, useState } from 'react';

import {
  getCategorySuggestionSettings,
  testCategorySuggestionModel,
  updateCategorySuggestionSettings,
  type CategorySuggestionSettings,
} from '../../../lib/api-client-category-suggestions';
import { AdminEditorPanel } from '../../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '../../ui/admin-field-grid';
import { Button } from '../../ui/button';
import { Card } from '../../ui/card';
import { Input } from '../../ui/input';
import { StatusBanner } from '../../status-banner';

type PendingAction = 'save' | 'test';

export function CategorySuggestionSettingsCard() {
  const [settings, setSettings] = useState<CategorySuggestionSettings | null>(
    null
  );
  const [fallbacks, setFallbacks] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState<PendingAction | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCategorySuggestionSettings()
      .then((row) => {
        if (cancelled) {
          return;
        }
        setSettings(row);
        setFallbacks((row.fallback_models || []).join(', '));
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    if (!settings) {
      return;
    }
    setPending('save');
    setError('');
    setNotice('');
    try {
      const updated = await updateCategorySuggestionSettings({
        ...settings,
        fallback_models: fallbacks
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setSettings(updated);
      setNotice('Settings saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setPending(null);
    }
  }

  async function testModel() {
    setPending('test');
    setError('');
    setNotice('');
    try {
      const result = await testCategorySuggestionModel(
        settings?.openrouter_model || undefined
      );
      setNotice(result.message || 'Model replied.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Model test failed.');
    } finally {
      setPending(null);
    }
  }

  if (!settings) {
    return (
      <Card>
        {error ? (
          <StatusBanner variant='error' title='Error'>
            {error}
          </StatusBanner>
        ) : (
          <p className='text-sm text-slate-600'>Loading settings...</p>
        )}
      </Card>
    );
  }

  const isSaving = pending !== null;

  return (
    <Card>
      <AdminEditorPanel
        status={
          <>
            {error ? (
              <StatusBanner variant='error' title='Error'>
                {error}
              </StatusBanner>
            ) : null}
            {notice ? (
              <StatusBanner variant='success' title='Saved'>
                {notice}
              </StatusBanner>
            ) : null}
          </>
        }
        actions={
          <>
            <Button
              type='button'
              onClick={() => void save()}
              disabled={isSaving}
              loading={pending === 'save'}
              loadingLabel='Saving…'
            >
              Save settings
            </Button>
            <Button
              type='button'
              variant='secondary'
              onClick={() => void testModel()}
              disabled={isSaving}
              loading={pending === 'test'}
              loadingLabel='Testing…'
            >
              Test model
            </Button>
          </>
        }
      >
        <AdminFieldGrid columns={2}>
          <AdminField label='Suggestion settings' span='full'>
            <p className='text-sm text-slate-600'>
              Capture is off until you turn it on. Saved model and fallbacks
              apply to the next enrichment. The test call is one short ping.
            </p>
          </AdminField>
          <AdminField span='full'>
            <label className='flex items-center gap-2 text-sm'>
              <input
                type='checkbox'
                checked={settings.on_import_enabled}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    on_import_enabled: event.target.checked,
                  })
                }
              />
              Capture unknown categories on import
            </label>
          </AdminField>
          <AdminField span='full'>
            <label className='flex items-center gap-2 text-sm'>
              <input
                type='checkbox'
                checked={settings.auto_enrich_enabled}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    auto_enrich_enabled: event.target.checked,
                  })
                }
              />
              Enrich new suggestions automatically
            </label>
          </AdminField>
          <AdminField span='full'>
            <label className='flex items-center gap-2 text-sm'>
              <input
                type='checkbox'
                checked={settings.deny_data_collection}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    deny_data_collection: event.target.checked,
                  })
                }
              />
              Deny provider data collection
            </label>
          </AdminField>
          <AdminField label='OpenRouter model' htmlFor='suggestion-model'>
            <Input
              id='suggestion-model'
              value={settings.openrouter_model || ''}
              placeholder={settings.default_openrouter_model || 'qwen/qwen3-30b-a3b'}
              onChange={(event) =>
                setSettings({ ...settings, openrouter_model: event.target.value })
              }
            />
          </AdminField>
          <AdminField label='Fallback models' htmlFor='suggestion-fallbacks'>
            <Input
              id='suggestion-fallbacks'
              value={fallbacks}
              placeholder='qwen/qwen-turbo'
              onChange={(event) => setFallbacks(event.target.value)}
            />
          </AdminField>
          <AdminField label='Max evidence items' htmlFor='suggestion-evidence'>
            <Input
              id='suggestion-evidence'
              type='number'
              min={5}
              max={50}
              value={settings.max_evidence_items}
              onChange={(event) =>
                setSettings({
                  ...settings,
                  max_evidence_items: Number(event.target.value),
                })
              }
            />
          </AdminField>
        </AdminFieldGrid>
      </AdminEditorPanel>
    </Card>
  );
}
