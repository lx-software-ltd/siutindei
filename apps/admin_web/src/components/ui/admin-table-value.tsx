import { Fragment, type ReactNode } from 'react';

import { clsx } from 'clsx';

import { formatDateTime } from '@/lib/date-utils';

import layout from './admin-table-cell-layout.json';

/** Missing table value. Every role uses this, not a blank or a prose empty. */
export const ADMIN_TABLE_EMPTY = '—';

/** Layout-only classes allowed on `AdminDataTableCell`. Content uses a role. */
export function isAdminTableCellLayoutClass(token: string): boolean {
  return (
    layout.exact.includes(token) ||
    layout.prefix.some((prefix) => token.startsWith(prefix) && token.length > prefix.length)
  );
}

export function adminTableCellClassNameError(className: string | undefined): string | null {
  if (!className) {
    return null;
  }
  for (const token of className.split(/\s+/)) {
    if (!token) {
      continue;
    }
    if (!isAdminTableCellLayoutClass(token)) {
      return `AdminDataTableCell class "${token}" is not a layout class. Use a table role component.`;
    }
  }
  return null;
}

export function adminTableText(value: string | null | undefined): string {
  const text = value?.trim();
  return text ? text : ADMIN_TABLE_EMPTY;
}

/** Snake_case tokens as words (`empty_address` → `empty address`). */
export function formatAdminTableLabel(value: string | null | undefined): string {
  const text = value?.trim();
  if (!text) {
    return ADMIN_TABLE_EMPTY;
  }
  return text.replaceAll('_', ' ');
}

export function formatAdminTableLabels(values: readonly string[] | null | undefined): string {
  const labels = (values ?? [])
    .map((value) => value.trim().replaceAll('_', ' '))
    .filter(Boolean);
  return labels.length ? labels.join(', ') : ADMIN_TABLE_EMPTY;
}

/** `fraction` is 0–1. `0.82` renders `82%`. */
export function formatAdminTablePercent(fraction: number | null | undefined): string {
  if (fraction == null || Number.isNaN(fraction)) {
    return ADMIN_TABLE_EMPTY;
  }
  return `${Math.round(fraction * 100)}%`;
}

/** En dash, no spaces: `3–12`. */
export function formatAdminTableRange(min: number, max: number): string {
  return `${min}–${max}`;
}

function isBlank(children: ReactNode): boolean {
  return children == null || (typeof children === 'string' && children.trim() === '');
}

function nameChildren(children: ReactNode): ReactNode {
  if (isBlank(children)) {
    return ADMIN_TABLE_EMPTY;
  }
  if (typeof children === 'string' && children.includes('@')) {
    return children.split(/([@.])/).map((part, index) =>
      part === '@' || part === '.' ? (
        <Fragment key={index}>
          <wbr />
          {part}
        </Fragment>
      ) : (
        part
      )
    );
  }
  return children;
}

/** Identifying label. One per row. */
export function AdminTableName({ children }: { children: ReactNode }) {
  return <span className='break-words font-medium'>{nameChildren(children)}</span>;
}

/** An instant. `emphasis` is for the row whose identity is the time. */
export function AdminTableTime({
  value,
  emphasis = false,
}: {
  value?: string | null;
  emphasis?: boolean;
}) {
  return (
    <span className={clsx('admin-table-time text-ink-700', emphasis && 'font-medium')}>
      {formatDateTime(value)}
    </span>
  );
}

/** Opaque token: ticket id, actor, job id, place id, source id, key prefix. */
export function AdminTableId({ children }: { children: ReactNode }) {
  return (
    <span className='admin-table-id font-mono text-xs text-ink-700'>
      {isBlank(children) ? ADMIN_TABLE_EMPTY : children}
    </span>
  );
}

/** Count, score, order, stars, percent, or range. */
export function AdminTableNumber({ children }: { children: ReactNode }) {
  return <span className='tabular-nums'>{isBlank(children) ? ADMIN_TABLE_EMPTY : children}</span>;
}
