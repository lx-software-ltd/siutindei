import Link from 'next/link';

import { DetailIcon } from './detail-icon';
import type { ActivityDetailCopy } from './types';

export interface BreadcrumbItem {
  readonly label: string;
  readonly href: string;
}

/** "Back to results" after a search, otherwise a trail into search. */
export function ActivityBreadcrumb({
  backHref,
  items,
  copy,
}: {
  readonly backHref: string | null;
  readonly items: readonly BreadcrumbItem[];
  readonly copy: ActivityDetailCopy;
}) {
  if (backHref) {
    return (
      <Link
        href={backHref}
        className="link-unadorned inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-ink-700 hover:text-ink-900"
      >
        <DetailIcon name="back" className="h-4 w-4" />
        {copy.backToResultsLabel}
      </Link>
    );
  }
  return (
    <nav aria-label={copy.breadcrumbLabel}>
      <ol className="flex min-h-11 flex-wrap items-center gap-x-2 text-sm text-ink-500">
        {items.map((item, index) => (
          <li key={item.href} className="flex items-center gap-2">
            {index > 0 ? <span aria-hidden="true">/</span> : null}
            <Link href={item.href} className="hover:text-ink-900">
              {item.label}
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  );
}
