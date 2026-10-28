'use client';

import type { Ticket } from '../../lib/api-client-user';
import { formatDateTime } from '../../lib/date-utils';
import { StatusBanner } from '../status-banner';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminInputCard } from '../ui/admin-input-card';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { StatusBadge } from '../ui/status-badge';

interface PendingRequestNoticeProps {
  request: Ticket;
}

export function PendingRequestNotice({ request }: PendingRequestNoticeProps) {
  return (
    <div className='space-y-4'>
      <StatusBanner kind='pending-review'>
        Your organization access request has been submitted and is pending review.
      </StatusBanner>
      <AdminInputCard
        title='Your request details'
        description='An administrator will review your request and get back to you.'
      >
        <AdminFieldGrid columns={2}>
            <AdminReadOnlyValue label='Ticket ID' mono>
              {request.ticket_id}
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Status'>
              <StatusBadge status={request.status} />
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Organization name' span={2}>
              {request.organization_name}
            </AdminReadOnlyValue>
            {request.message ? (
              <AdminReadOnlyValue label='Your message' span={2}>
                {request.message}
              </AdminReadOnlyValue>
            ) : null}
            <AdminReadOnlyValue label='Submitted'>
              {formatDateTime(request.created_at)}
            </AdminReadOnlyValue>
          </AdminFieldGrid>
        <p className='text-sm text-ink-700'>
          You will be notified once your request has been reviewed. In the
          meantime, you cannot submit another request. If you have any
          questions, please contact support.
        </p>
      </AdminInputCard>
    </div>
  );
}
