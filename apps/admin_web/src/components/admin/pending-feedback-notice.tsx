'use client';

import { useEffect, useMemo, useState } from 'react';

import { listFeedbackLabels, type Ticket } from '../../lib/api-client-user';
import { formatDateTime } from '../../lib/date-utils';
import type { FeedbackLabel } from '../../types/admin';
import { StatusBanner } from '../status-banner';
import { AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminReadOnlyValue } from '../ui/admin-read-only-value';
import { Card } from '../ui/card';
import { StatusBadge } from '../ui/status-badge';

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
      <StatusBanner kind='pending-review'>
        Your feedback is being reviewed by our team. We&apos;ll notify you
        once it&apos;s been processed.
      </StatusBanner>
      <Card
        title='Your Feedback'
        description='Thank you for sharing your experience!'
      >
        <AdminEditorPanel>
          <AdminFieldGrid columns={2}>
            <AdminReadOnlyValue label='Ticket ID' mono>
              {feedback.ticket_id}
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Status'>
              <StatusBadge status={feedback.status} />
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Organization' span={2}>
              {feedback.organization_name}
            </AdminReadOnlyValue>
            <AdminReadOnlyValue label='Stars'>
              {feedback.feedback_stars ?? '—'}
            </AdminReadOnlyValue>
            {labelNames && labelNames.length > 0 ? (
              <AdminReadOnlyValue label='Labels'>
                {labelNames.join(', ')}
              </AdminReadOnlyValue>
            ) : null}
            {feedback.feedback_text ? (
              <AdminReadOnlyValue label='Description' span={2}>
                {feedback.feedback_text}
              </AdminReadOnlyValue>
            ) : null}
            <AdminReadOnlyValue label='Submitted'>
              {formatDateTime(feedback.created_at)}
            </AdminReadOnlyValue>
          </AdminFieldGrid>
          <p className='text-sm text-slate-600'>
            You can submit another feedback entry once this one has been reviewed.
          </p>
        </AdminEditorPanel>
      </Card>
    </div>
  );
}
