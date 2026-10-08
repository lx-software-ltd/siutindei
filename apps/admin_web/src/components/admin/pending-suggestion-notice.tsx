'use client';

import type { Ticket } from '../../lib/api-client-user';
import { formatDateTime } from '../../lib/date-utils';
import { Card } from '../ui/card';
import { StatusBadge } from '../ui/status-badge';
import { StatusBanner } from '../status-banner';

interface PendingSuggestionNoticeProps {
  suggestion: Ticket;
}

export function PendingSuggestionNotice({
  suggestion,
}: PendingSuggestionNoticeProps) {
  return (
    <div className='space-y-4'>
      <StatusBanner variant='info' kind='pending-review'>
        Your suggestion is being reviewed by our team. We&apos;ll notify you once
        it&apos;s been processed.
      </StatusBanner>
      <Card
        title='Your Suggestion'
        description='Thank you for helping us discover new places!'
      >
        <dl className='space-y-4'>
          <div className='flex items-start justify-between gap-3'>
            <div>
              <dt className='text-sm font-medium text-slate-500'>Ticket ID</dt>
              <dd className='mt-1 font-mono text-sm text-slate-900'>
                {suggestion.ticket_id}
              </dd>
            </div>
            <StatusBadge status={suggestion.status} />
          </div>
          <div>
            <dt className='text-sm font-medium text-slate-500'>Organization Name</dt>
            <dd className='mt-1 text-sm text-slate-900'>{suggestion.organization_name}</dd>
          </div>
          {suggestion.description ? (
            <div>
              <dt className='text-sm font-medium text-slate-500'>Description</dt>
              <dd className='mt-1 text-sm text-slate-900'>{suggestion.description}</dd>
            </div>
          ) : null}
          {suggestion.suggested_district ? (
            <div>
              <dt className='text-sm font-medium text-slate-500'>District</dt>
              <dd className='mt-1 text-sm text-slate-900'>{suggestion.suggested_district}</dd>
            </div>
          ) : null}
          {suggestion.suggested_address ? (
            <div>
              <dt className='text-sm font-medium text-slate-500'>Address</dt>
              <dd className='mt-1 text-sm text-slate-900'>{suggestion.suggested_address}</dd>
            </div>
          ) : null}
          <div>
            <dt className='text-sm font-medium text-slate-500'>Submitted</dt>
            <dd className='mt-1 text-sm text-slate-900'>
              {formatDateTime(suggestion.created_at)}
            </dd>
          </div>
        </dl>
        <p className='mt-4 text-sm text-slate-600'>
          You can submit another suggestion once this one has been reviewed.
        </p>
      </Card>
    </div>
  );
}
