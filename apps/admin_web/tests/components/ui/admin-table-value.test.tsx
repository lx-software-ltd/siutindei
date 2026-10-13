import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { IdentityProviderBadge } from '@/components/admin/cognito-users/badges';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { ResourceTableShell } from '@/components/ui/resource-table-shell';
import {
  ADMIN_TABLE_EMPTY,
  AdminTableId,
  AdminTableName,
  AdminTableNumber,
  AdminTableTime,
  adminTableCellClassNameError,
  formatAdminTableLabel,
  formatAdminTableLabels,
  formatAdminTablePercent,
  formatAdminTableRange,
} from '@/components/ui/admin-table-value';

describe('table cell roles', () => {
  it('renders a name in medium weight and an em dash when blank', () => {
    render(
      <>
        <AdminTableName>Harbour Club</AdminTableName>
        <AdminTableName> </AdminTableName>
      </>
    );

    expect(screen.getByText('Harbour Club')).toHaveClass('font-medium');
    expect(screen.getByText('Harbour Club').className).not.toContain('truncate');
    expect(screen.getAllByText(ADMIN_TABLE_EMPTY).length).toBeGreaterThan(0);
  });

  it('prefers email breaks at @ and . instead of mid-word', () => {
    const { container } = render(<AdminTableName>manager@example.com</AdminTableName>);
    const name = container.querySelector('span.font-medium');

    expect(name).toHaveClass('break-words');
    expect(name?.textContent).toBe('manager@example.com');
    expect(name?.querySelectorAll('wbr').length).toBe(2);
  });

  it('renders a time in slate-600 and emphasises the row identity', () => {
    const afternoon = new Date(2026, 9, 13, 14, 36);
    render(
      <>
        <AdminTableTime value={afternoon.toISOString()} />
        <AdminTableTime value={afternoon.toISOString()} emphasis />
        <AdminTableTime value={null} />
      </>
    );

    const times = screen.getAllByText('Oct 13, 02:36 PM');
    expect(times[0]).toHaveClass('text-slate-600');
    expect(times[0].className).not.toContain('font-medium');
    expect(times[1]).toHaveClass('font-medium', 'text-slate-600');
    expect(screen.getByText(ADMIN_TABLE_EMPTY)).toHaveClass('text-slate-600');
  });

  it('renders an id in mono and an em dash when blank', () => {
    render(
      <>
        <AdminTableId>job-1</AdminTableId>
        <AdminTableId>{''}</AdminTableId>
      </>
    );

    expect(screen.getByText('job-1')).toHaveClass('font-mono', 'text-xs', 'text-slate-600');
    expect(screen.getByText(ADMIN_TABLE_EMPTY)).toBeInTheDocument();
  });

  it('renders numbers, percents, and ranges', () => {
    render(
      <>
        <AdminTableNumber>{4}</AdminTableNumber>
        <AdminTableNumber>{formatAdminTablePercent(0.82)}</AdminTableNumber>
        <AdminTableNumber>{formatAdminTableRange(3, 12)}</AdminTableNumber>
        <AdminTableNumber>{null}</AdminTableNumber>
      </>
    );

    expect(screen.getByText('4')).toHaveClass('tabular-nums');
    expect(screen.getByText('82%')).toHaveClass('tabular-nums');
    expect(screen.getByText('3–12')).toHaveClass('tabular-nums');
    expect(screen.getByText(ADMIN_TABLE_EMPTY)).toHaveClass('tabular-nums');
  });

  it('turns snake_case tokens into words', () => {
    expect(formatAdminTableLabel('empty_address')).toBe('empty address');
    expect(formatAdminTableLabels(['empty_address', 'missing_pin'])).toBe(
      'empty address, missing pin'
    );
    expect(formatAdminTableLabels([])).toBe(ADMIN_TABLE_EMPTY);
    expect(formatAdminTablePercent(null)).toBe(ADMIN_TABLE_EMPTY);
    expect(formatAdminTablePercent(0.823)).toBe('82%');
    expect(formatAdminTableLabel('pending_review')).toBe('pending review');
  });

  it('warns on a content class without taking the page down', () => {
    expect(adminTableCellClassNameError('w-10 pr-0')).toBeNull();
    expect(adminTableCellClassNameError('w-px whitespace-nowrap text-right')).toBeNull();
    expect(adminTableCellClassNameError('font-medium')).toMatch(/layout class/);
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    render(<AdminDataTableCell className='text-slate-600'>Ada</AdminDataTableCell>);

    expect(warn).toHaveBeenCalledWith(expect.stringMatching(/layout class/));
    expect(screen.getByText('Ada')).toBeInTheDocument();
    warn.mockRestore();
  });

  it('labels an empty phone caption with the column name', () => {
    render(
      <AdminDataTableCellMeta label='Expires' empty>
        <AdminTableTime value={null} />
      </AdminDataTableCellMeta>
    );

    expect(screen.getByText(`Expires ${ADMIN_TABLE_EMPTY}`)).toBeInTheDocument();
  });

  it('exposes the provider icon to assistive tech', () => {
    render(<IdentityProviderBadge username='manager@example.com' />);

    expect(screen.getByRole('img', { name: 'Email' })).toBeInTheDocument();
  });
});

describe('ResourceTableShell draft cells', () => {
  it('puts the draft label in the name cell and hides later columns with the header priority', () => {
    render(
      <ResourceTableShell
        ariaLabel='Labels'
        rows={[]}
        getLabel={() => 'Ada'}
        middleColumnCount={2}
        hasActions={false}
        isLoading={false}
        isExpanded={() => false}
        onToggle={() => undefined}
        isDraftOpen
        draftLabel='New label'
        onToggleDraft={() => undefined}
        detail={null}
        head={
          <>
            <AdminDataTableHeadCell>Label</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Order</AdminDataTableHeadCell>
          </>
        }
        renderCells={() => <AdminDataTableCell>Ada</AdminDataTableCell>}
      />
    );

    expect(screen.getByText('New label')).toHaveClass('font-medium');
    expect(screen.getByText(ADMIN_TABLE_EMPTY).closest('td')).toHaveClass(
      'hidden',
      'md:table-cell'
    );
  });
});
