import { Fragment } from 'react';

import { clsx } from 'clsx';

import { highlightAuditJson } from '@/lib/audit-value-highlight';

export function AuditHighlightedJson({
  value,
  counterpart,
  changedFields,
  className,
  emphasisClassName,
  'aria-label': ariaLabel,
}: {
  value: Record<string, unknown>;
  counterpart?: Record<string, unknown> | null;
  changedFields?: readonly string[] | null;
  className: string;
  emphasisClassName: string;
  'aria-label': string;
}) {
  const segments = highlightAuditJson({ value, counterpart, changedFields });
  return (
    <pre className={className} aria-label={ariaLabel}>
      {segments.map((segment, index) => (
        <Fragment key={index}>
          {segment.emphasize ? (
            <span
              data-audit-changed='true'
              className={clsx('rounded-sm px-0.5', emphasisClassName)}
            >
              {segment.text}
            </span>
          ) : (
            segment.text
          )}
        </Fragment>
      ))}
    </pre>
  );
}
