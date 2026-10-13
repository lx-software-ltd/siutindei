'use client';

import type { Ticket } from '../../lib/api-client-user';
import { formatDateTime } from '../../lib/date-utils';
import { StatusBanner } from '../status-banner';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminInputCard } from '../ui/admin-input-card';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { StatusBadge } from '../ui/status-badge';

interface PendingSuggestionNoticeProps {
  suggestion: Ticket;
}

export function PendingSuggestionNotice({
  suggestion,
}: PendingSuggestionNoticeProps) {
  return (
    <div className='space-y-4'>
      <StatusBanner kind='pending-review'>
        Your suggestion is being reviewed by our team. We&apos;ll notify you once
        it&apos;s been processed.
      </StatusBanner>
      <AdminInputCard
        title='Your suggestion'
        description='Thank you for helping us discover new places!'
      >
        <AdminFieldGrid columns={2}>
            <AdminReadOnlyValue label='Ticket ID' mono>
              {suggestion.ticket_id}
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Status'>
              <StatusBadge status={suggestion.status} />
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Organization name' span={2}>
              {suggestion.organization_name}
            </AdminReadOnlyValue>
            {suggestion.description ? (
              <AdminReadOnlyValue label='Description' span={2}>
                {suggestion.description}
              </AdminReadOnlyValue>
            ) : null}
            {suggestion.suggested_district ? (
              <AdminReadOnlyValue label='District'>
                {suggestion.suggested_district}
              </AdminReadOnlyValue>
            ) : null}
            {suggestion.suggested_address ? (
              <AdminReadOnlyValue label='Address'>
                {suggestion.suggested_address}
              </AdminReadOnlyValue>
            ) : null}
            <AdminReadOnlyValue label='Submitted'>
              {formatDateTime(suggestion.created_at)}
            </AdminReadOnlyValue>
          </AdminFieldGrid>
        <p className='text-sm text-slate-600'>
          You can submit another suggestion once this one has been reviewed.
        </p>
      </AdminInputCard>
    </div>
  );
}
