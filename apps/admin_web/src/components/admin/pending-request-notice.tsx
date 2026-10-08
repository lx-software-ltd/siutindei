'use client';

import type { Ticket } from '../../lib/api-client-user';
import { formatDateTime } from '../../lib/date-utils';
import { Card } from '../ui/card';
import { StatusBanner } from '../status-banner';
import { StatusBadge } from '../ui/status-badge';

interface PendingRequestNoticeProps {
  request: Ticket;
}

export function PendingRequestNotice({ request }: PendingRequestNoticeProps) {
  const formattedDate = formatDateTime(request.created_at);

  return (
    <div className='space-y-4'>
      <StatusBanner kind='pending-review'>
        Your organization access request has been submitted and is pending review.
      </StatusBanner>

      <div className='mt-6'>
        <Card
          title='Your Request Details'
          description='An administrator will review your request and get back to you.'
        >
          <div className='space-y-4'>
            <div>
              <dt className='text-sm font-medium text-slate-500'>Ticket ID</dt>
              <dd className='mt-1 font-mono text-sm text-slate-900'>
                {request.ticket_id}
              </dd>
            </div>

            <div>
              <dt className='text-sm font-medium text-slate-500'>
                Organization Name
              </dt>
              <dd className='mt-1 text-sm text-slate-900'>
                {request.organization_name}
              </dd>
            </div>

            {request.message && (
              <div>
                <dt className='text-sm font-medium text-slate-500'>
                  Your Message
                </dt>
                <dd className='mt-1 text-sm text-slate-900'>
                  {request.message}
                </dd>
              </div>
            )}

            <div>
              <dt className='text-sm font-medium text-slate-500'>
                Submitted On
              </dt>
              <dd className='mt-1 text-sm text-slate-900'>{formattedDate}</dd>
            </div>

            <div>
              <dt className='text-sm font-medium text-slate-500'>Status</dt>
              <dd className='mt-1'>
                <StatusBadge status={request.status} />
              </dd>
            </div>
          </div>

          <div className='mt-6 rounded-md bg-slate-50 p-3 sm:p-4'>
            <p className='text-xs text-slate-600 sm:text-sm'>
              You will be notified once your request has been reviewed. In the
              meantime, you cannot submit another request. If you have any
              questions, please contact support.
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}
