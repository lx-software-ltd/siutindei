'use client';

import { AdminField } from '../../ui/admin-field-grid';
import { AdminInputCard } from '../../ui/admin-input-card';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';

export const SWEEP_TIMEOUT_MESSAGE =
  'The sweep did not answer in time. It may still have run; refresh in a moment and sweep again to continue.';

export function sweepLimitNote(truncated: boolean): string {
  return truncated
    ? ' Stopped at the limit; sweep again to continue with the rest. The pending count falls when you apply or dismiss findings, not when you sweep.'
    : '';
}

export function ReviewQueueScopeNote({ onClear }: { onClear: () => void }) {
  return (
    <p className='text-sm text-ink-700'>
      Filtered to the organization from the review queue. Sweep pending only
      includes organizations still in review. Sweep all orgs includes this
      organization when it is already approved.{' '}
      <button type='button' className='underline' onClick={onClear}>
        Show all
      </button>
    </p>
  );
}

export function ModelBudgetCard({
  monthCost,
  limit,
  value,
  onChange,
  onSave,
  inputId,
  description,
}: {
  monthCost: number;
  limit: number;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  inputId: string;
  description: string;
}) {
  return (
    <AdminInputCard
      title='Model budget'
      titleLevel='h3'
      description={`This month ${monthCost} of ${limit} USD. ${description}`}
      actions={
        <Button type='button' variant='secondary' onClick={onSave}>
          Save budget
        </Button>
      }
    >
      <AdminField label='Monthly limit (USD)' htmlFor={inputId}>
        <Input
          id={inputId}
          inputMode='decimal'
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </AdminField>
    </AdminInputCard>
  );
}
