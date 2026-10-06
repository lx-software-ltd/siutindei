'use client';

import { parseAsString, useQueryStates } from 'nuqs';

import { AdminTabStrip } from '../ui/admin-tab-strip';
import { FeedbackLabelsPanel } from './feedback-labels-panel';
import { FeedbackPanel } from './feedback-panel';

type FeedbackView = 'entries' | 'labels';

const FEEDBACK_VIEWS = [
  { key: 'entries' as const, label: 'Feedback' },
  { key: 'labels' as const, label: 'Feedback Labels' },
];

export function FeedbackPage() {
  const [query, setQuery] = useQueryStates({
    section: parseAsString,
    feedbackView: parseAsString,
  });
  const activeView: FeedbackView =
    query.feedbackView === 'labels' || query.feedbackView === 'entries'
      ? query.feedbackView
      : query.section === 'feedback-labels'
        ? 'labels'
        : 'entries';

  return (
    <div className='space-y-4'>
      <AdminTabStrip
        aria-label='Feedback'
        items={FEEDBACK_VIEWS}
        activeKey={activeView}
        onChange={(key) => {
          void setQuery({
            section: 'feedback',
            feedbackView: key === 'entries' ? null : 'labels',
          });
        }}
      />
      {activeView === 'labels' ? <FeedbackLabelsPanel /> : <FeedbackPanel />}
    </div>
  );
}
