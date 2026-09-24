'use client';

import { useEffect, useState } from 'react';

import {
  getCategorySuggestionSettings,
  testCategorySuggestionModel,
  updateCategorySuggestionSettings,
  type CategorySuggestionSettings,
} from '../../../lib/api-client-category-suggestions';
import { Button } from '../../ui/button';
import { Card } from '../../ui/card';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { StatusBanner } from '../../status-banner';

export function CategorySuggestionSettingsCard() {
  const [settings, setSettings] = useState<CategorySuggestionSettings | null>(
    null
  );
  const [fallbacks, setFallbacks] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isSaving, setIsSaving] = useState(false);

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
    setIsSaving(true);
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
      setIsSaving(false);
    }
  }

  async function testModel() {
    setIsSaving(true);
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
      setIsSaving(false);
    }
  }

  if (!settings) {
    return (
      <Card title='Suggestion settings' description='Loading settings.'>
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

  return (
    <Card
      title='Suggestion settings'
      description='Capture is off until you turn it on. Saved model and fallbacks apply to the next enrichment. The test call is one short ping.'
    >
      {error ? (
        <div className='mb-4'>
          <StatusBanner variant='error' title='Error'>
            {error}
          </StatusBanner>
        </div>
      ) : null}
      {notice ? (
        <div className='mb-4'>
          <StatusBanner variant='success' title='Saved'>
            {notice}
          </StatusBanner>
        </div>
      ) : null}
      <div className='grid gap-4 md:grid-cols-2'>
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
        <div className='space-y-1'>
          <Label htmlFor='suggestion-model'>OpenRouter model</Label>
          <Input
            id='suggestion-model'
            value={settings.openrouter_model || ''}
            placeholder={settings.default_openrouter_model || 'qwen/qwen3-30b-a3b'}
            onChange={(event) =>
              setSettings({ ...settings, openrouter_model: event.target.value })
            }
          />
        </div>
        <div className='space-y-1'>
          <Label htmlFor='suggestion-fallbacks'>Fallback models</Label>
          <Input
            id='suggestion-fallbacks'
            value={fallbacks}
            placeholder='qwen/qwen-turbo'
            onChange={(event) => setFallbacks(event.target.value)}
          />
        </div>
        <div className='space-y-1'>
          <Label htmlFor='suggestion-evidence'>Max evidence items</Label>
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
        </div>
      </div>
      <div className='mt-4 flex flex-wrap gap-3'>
        <Button type='button' onClick={() => void save()} disabled={isSaving}>
          Save settings
        </Button>
        <Button
          type='button'
          variant='secondary'
          onClick={() => void testModel()}
          disabled={isSaving}
        >
          Test model
        </Button>
      </div>
    </Card>
  );
}
