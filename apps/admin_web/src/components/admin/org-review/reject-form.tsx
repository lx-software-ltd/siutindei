'use client';

import { Label } from '../../ui/label';
import { RequiredMark } from '../../ui/admin-field-grid';
import { Select } from '../../ui/select';
import { Textarea } from '../../ui/textarea';

export const REVIEW_REASON_OPTIONS = [
  ['not_relevant', 'Not relevant'],
  ['duplicate', 'Duplicate'],
  ['poor_data', 'Poor data'],
  ['other', 'Other'],
] as const;

const REASON_LABELS = Object.fromEntries(REVIEW_REASON_OPTIONS);

export function reviewReasonLabel(reason: string | null | undefined): string | undefined {
  if (!reason) {
    return undefined;
  }
  return REASON_LABELS[reason];
}

interface RejectFormProps {
  reason: string;
  notes: string;
  hideListing: boolean;
  disabled?: boolean;
  onReason: (reason: string) => void;
  onNotes: (notes: string) => void;
  onHideListing: (hide: boolean) => void;
}

export function RejectForm({
  reason,
  notes,
  hideListing,
  disabled = false,
  onReason,
  onNotes,
  onHideListing,
}: RejectFormProps) {
  return (
    <div className='space-y-4'>
      <div>
        <Label htmlFor='reject-reason'>
          Reject reason
          <RequiredMark />
        </Label>
        <Select
          id='reject-reason'
          value={reason}
          disabled={disabled}
          onChange={(event) => onReason(event.target.value)}
        >
          <option value=''>Choose a reason</option>
          {REVIEW_REASON_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor='reject-notes'>Notes</Label>
        <Textarea
          id='reject-notes'
          value={notes}
          disabled={disabled}
          rows={3}
          onChange={(event) => onNotes(event.target.value)}
        />
      </div>
      <label className='flex items-center gap-2 text-sm text-ink-700'>
        <input
          type='checkbox'
          checked={hideListing}
          disabled={disabled}
          onChange={(event) => onHideListing(event.target.checked)}
        />
        Hide from public listing
      </label>
    </div>
  );
}
