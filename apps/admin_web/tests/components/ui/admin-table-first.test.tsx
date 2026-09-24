import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AdminCreateButton } from '@/components/ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminEditorActions } from '@/components/ui/admin-editor-panel';
import { AdminFilterBar } from '@/components/ui/admin-filter-bar';
import { AdminRecordTable } from '@/components/ui/admin-record-table';
import { Button } from '@/components/ui/button';

describe('AdminRecordTable', () => {
  it('renders filters and an empty state inside one untitled card', () => {
    render(
      <AdminRecordTable
        aria-label='Organizations'
        columnCount={2}
        rowCount={0}
        isLoading={false}
        filters={<AdminFilterBar trailing={<AdminCreateButton label='New organization' onClick={() => undefined} />} />}
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Status</AdminDataTableHeadCell>
          </>
        }
      >
        {null}
      </AdminRecordTable>
    );

    expect(screen.getByTestId('admin-record-table')).toBeInTheDocument();
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New organization' })).toBeVisible();
    expect(screen.getByText('No records match the current filters.')).toBeVisible();
  });

  it('shows skeleton rows while the first page loads', () => {
    render(
      <AdminRecordTable
        aria-label='Organizations'
        columnCount={1}
        rowCount={0}
        isLoading
        head={<AdminDataTableHeadCell>Name</AdminDataTableHeadCell>}
      >
        {null}
      </AdminRecordTable>
    );

    expect(screen.getAllByTestId('admin-skeleton-row').length).toBeGreaterThan(0);
  });
});

describe('AdminDataTable column priority', () => {
  it('hides secondary cells below the md breakpoint', () => {
    render(
      <table>
        <tbody>
          <tr>
            <AdminDataTableCell>Name</AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>Manager</AdminDataTableCell>
          </tr>
        </tbody>
      </table>
    );

    expect(screen.getByText('Manager').className).toContain('md:table-cell');
    expect(screen.getByText('Name').className).toContain('max-md:wrap-anywhere');
  });
});

describe('AdminEditorActions', () => {
  it('renders one primary action and no cancel button', async () => {
    const onSubmit = vi.fn();
    render(<AdminEditorActions mode='edit' onSubmit={onSubmit} />);

    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Update' }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });
});

describe('Button loading', () => {
  it('swaps the label for a busy saving state', () => {
    render(
      <Button type='button' loading>
        Update
      </Button>
    );

    const button = screen.getByRole('button', { name: 'Saving…' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
  });
});
