'use client';

import { useState } from 'react';

import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Select } from '../../ui/select';

const FIELD_OPTIONS = [
  { key: 'status', label: 'Listing status' },
  { key: 'source', label: 'Source' },
  { key: 'description_source', label: 'Description source' },
  { key: 'manager_id', label: 'Manager id' },
  { key: 'email', label: 'Email' },
  { key: 'phone_country_code', label: 'Phone country' },
  { key: 'phone_number', label: 'Phone number' },
  { key: 'whatsapp', label: 'WhatsApp' },
  { key: 'facebook', label: 'Facebook' },
  { key: 'instagram', label: 'Instagram' },
  { key: 'tiktok', label: 'TikTok' },
  { key: 'twitter', label: 'Twitter' },
  { key: 'xiaohongshu', label: 'Xiaohongshu' },
  { key: 'wechat', label: 'WeChat' },
  { key: 'review_notes', label: 'Review notes' },
] as const;

type FieldKey = (typeof FIELD_OPTIONS)[number]['key'];

interface BulkFieldsDialogProps {
  isSaving: boolean;
  onCancel: () => void;
  onApply: (fields: Record<string, string>) => void;
  onInvalid: (message: string) => void;
}

export function BulkFieldsDialog({
  isSaving,
  onCancel,
  onApply,
  onInvalid,
}: BulkFieldsDialogProps) {
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({
    status: 'operational',
    description_source: 'official',
  });

  function toggle(key: FieldKey) {
    setEnabled((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function submit() {
    const fields: Record<string, string> = {};
    for (const option of FIELD_OPTIONS) {
      if (!enabled[option.key]) {
        continue;
      }
      fields[option.key] = values[option.key] ?? '';
    }
    if ('manager_id' in fields && !fields.manager_id.trim()) {
      onInvalid('Enter a manager id, or untick that property.');
      return;
    }
    onApply(fields);
  }

  return (
    <div className='space-y-4 rounded-lg border border-slate-200 p-4'>
      <p className='text-sm text-slate-700'>
        Only the ticked fields are written. Empty text clears that field.
        Manager id cannot be cleared.
      </p>
      <div className='grid gap-3 md:grid-cols-2'>
        {FIELD_OPTIONS.map((option) => (
          <div key={option.key} className='space-y-1'>
            <label className='flex items-center gap-2 text-sm text-slate-800'>
              <input
                type='checkbox'
                checked={Boolean(enabled[option.key])}
                onChange={() => toggle(option.key)}
              />
              {option.label}
            </label>
            {option.key === 'status' ? (
              <Select
                aria-label='Listing status'
                value={values.status}
                disabled={!enabled.status}
                onChange={(event) =>
                  setValues((prev) => ({ ...prev, status: event.target.value }))
                }
              >
                <option value='operational'>Operational</option>
                <option value='closed_temporarily'>Closed temporarily</option>
                <option value='closed_permanently'>Closed permanently</option>
                <option value='hidden'>Hidden</option>
              </Select>
            ) : option.key === 'description_source' ? (
              <Select
                aria-label='Description source'
                value={values.description_source}
                disabled={!enabled.description_source}
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    description_source: event.target.value,
                  }))
                }
              >
                <option value='official'>Official</option>
                <option value='template'>Template</option>
                <option value='places'>Places</option>
                <option value='enrich'>Enrich</option>
              </Select>
            ) : (
              <Input
                aria-label={option.label}
                value={values[option.key] ?? ''}
                disabled={!enabled[option.key]}
                onChange={(event) =>
                  setValues((prev) => ({
                    ...prev,
                    [option.key]: event.target.value,
                  }))
                }
              />
            )}
          </div>
        ))}
      </div>
      <div className='flex flex-wrap gap-2'>
        <Button type='button' onClick={submit} disabled={isSaving}>
          Apply to selected
        </Button>
        <Button type='button' variant='secondary' onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
