'use client';

import { useEffect, useMemo, useState } from 'react';

import { listFeedbackLabels, type Ticket } from '../../lib/api-client-user';
import { formatDateTime } from '../../lib/date-utils';
import type { FeedbackLabel } from '../../types/admin';
import { Card } from '../ui/card';
import { StatusBadge } from '../ui/status-badge';
import { StatusBanner } from '../status-banner';

interface PendingFeedbackNoticeProps {
  feedback: Ticket;
}

export function PendingFeedbackNotice({
  feedback,
}: PendingFeedbackNoticeProps) {
  const [labels, setLabels] = useState<FeedbackLabel[]>([]);

  useEffect(() => {
    const loadLabels = async () => {
      try {
        const response = await listFeedbackLabels();
        setLabels(response.items);
      } catch {
        setLabels([]);
      }
    };
    loadLabels();
  }, []);

  const labelNames = useMemo(() => {
    const map = new Map(labels.map((label) => [label.id, label.name]));
    return feedback.feedback_label_ids?.map(
      (id) => map.get(id) || id
    );
  }, [feedback.feedback_label_ids, labels]);

  return (
    <div className='space-y-4'>
      <StatusBanner variant='info' kind='pending-review'>
        Your feedback is being reviewed by our team. We&apos;ll notify you
        once it&apos;s been processed.
      </StatusBanner>
      <Card
        title='Your Feedback'
        description='Thank you for sharing your experience!'
      >
        <dl className='space-y-4'>
          <div className='flex items-start justify-between gap-3'>
            <div>
              <dt className='text-sm font-medium text-slate-500'>Ticket ID</dt>
              <dd className='mt-1 font-mono text-sm text-slate-900'>
                {feedback.ticket_id}
              </dd>
            </div>
            <StatusBadge status={feedback.status} />
          </div>
          <div>
            <dt className='text-sm font-medium text-slate-500'>Organization</dt>
            <dd className='mt-1 text-sm text-slate-900'>{feedback.organization_name}</dd>
          </div>
          <div>
            <dt className='text-sm font-medium text-slate-500'>Stars</dt>
            <dd className='mt-1 text-sm text-slate-900'>{feedback.feedback_stars ?? '—'}</dd>
          </div>
          {labelNames && labelNames.length > 0 ? (
            <div>
              <dt className='text-sm font-medium text-slate-500'>Labels</dt>
              <dd className='mt-1 text-sm text-slate-900'>{labelNames.join(', ')}</dd>
            </div>
          ) : null}
          {feedback.feedback_text ? (
            <div>
              <dt className='text-sm font-medium text-slate-500'>Description</dt>
              <dd className='mt-1 text-sm text-slate-900'>{feedback.feedback_text}</dd>
            </div>
          ) : null}
          <div>
            <dt className='text-sm font-medium text-slate-500'>Submitted</dt>
            <dd className='mt-1 text-sm text-slate-900'>
              {formatDateTime(feedback.created_at)}
            </dd>
          </div>
        </dl>
        <p className='mt-4 text-sm text-slate-600'>
          You can submit another feedback entry once this one has been reviewed.
        </p>
      </Card>
    </div>
  );
}
