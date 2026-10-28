'use client';

import { useEffect, useState } from 'react';

import {
  getEnrichmentSettings,
  updateEnrichmentSettings,
  type EnrichmentSettings,
} from '../../lib/api-client-enrichment';
import { ApiError } from '../../lib/api-client';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { StatusBanner } from '../status-banner';

const EMPTY: EnrichmentSettings = {
  monthly_cost_limit_usd: 25,
  max_pages: 12,
  max_page_bytes: 1000000,
  copy_media: true,
  min_confidence_shown: 0.5,
};

export function OrganizationEnrichmentSettings() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<EnrichmentSettings>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const [seenOpen, setSeenOpen] = useState(open);
  if (open !== seenOpen) {
    setSeenOpen(open);
    if (open) {
      setLoading(true);
      setError('');
    }
  }

  useEffect(() => {
    if (!open) {
      return;
    }
    let cancelled = false;
    getEnrichmentSettings()
      .then((row) => {
        if (!cancelled) {
          setForm(row);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Settings could not be loaded.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function save() {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      const row = await updateEnrichmentSettings(form);
      setForm(row);
      setSaved(true);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Settings could not be saved.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className='mt-4 border-t border-brand-100 pt-3'>
      <Button
        type='button'
        variant='secondary'
        size='md'
        data-testid='enrichment-settings'
        onClick={() => setOpen((current) => !current)}
      >
        Crawl limits
      </Button>
      {open ? (
        <div className='mt-3 grid max-w-xl gap-3'>
          {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
          {saved ? <StatusBanner kind='saved'>Crawl limits saved.</StatusBanner> : null}
          <div>
            <Label htmlFor='enrich-budget'>Monthly budget (USD)</Label>
            <Input
              id='enrich-budget'
              type='number'
              min={0.01}
              max={1000}
              step='0.01'
              disabled={loading}
              value={form.monthly_cost_limit_usd}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  monthly_cost_limit_usd: Number(event.target.value),
                }))
              }
            />
          </div>
          <div>
            <Label htmlFor='enrich-pages'>Pages per site</Label>
            <Input
              id='enrich-pages'
              type='number'
              min={1}
              max={20}
              disabled={loading}
              value={form.max_pages}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  max_pages: Number(event.target.value),
                }))
              }
            />
          </div>
          <div>
            <Label htmlFor='enrich-bytes'>Bytes per page</Label>
            <Input
              id='enrich-bytes'
              type='number'
              min={10000}
              max={2000000}
              disabled={loading}
              value={form.max_page_bytes}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  max_page_bytes: Number(event.target.value),
                }))
              }
            />
          </div>
          <div>
            <Label htmlFor='enrich-confidence'>Minimum confidence</Label>
            <Input
              id='enrich-confidence'
              type='number'
              min={0}
              max={1}
              step='0.05'
              disabled={loading}
              value={form.min_confidence_shown}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  min_confidence_shown: Number(event.target.value),
                }))
              }
            />
          </div>
          <label className='flex items-center gap-2 text-sm text-ink-700'>
            <input
              type='checkbox'
              checked={form.copy_media}
              disabled={loading}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  copy_media: event.target.checked,
                }))
              }
            />
            Copy images into catalog storage
          </label>
          <div>
            <Button
              type='button'
              variant='secondary'
              loading={saving}
              loadingLabel='Saving…'
              disabled={loading}
              onClick={() => void save()}
            >
              Save limits
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
