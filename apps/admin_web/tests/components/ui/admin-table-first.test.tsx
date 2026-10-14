import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AdminCreateButton } from '@/components/ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminFilterBar, AdminFilterField } from '@/components/ui/admin-filter-bar';
import { AdminRecordTable } from '@/components/ui/admin-record-table';
import { ResourceTableShell } from '@/components/ui/resource-table-shell';
import { Button } from '@/components/ui/button';

function following(a: HTMLElement, b: HTMLElement) {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('AdminCreateButton', () => {
  it('matches Button md height and stays auto-width', () => {
    render(<AdminCreateButton label='New organization' onClick={() => undefined} />);

    const create = screen.getByRole('button', { name: 'New organization' });
    expect(create).toHaveClass('h-10', 'px-4', 'sm:h-9', 'disabled:opacity-60');
    expect(create.className).not.toMatch(/\bw-full\b/);
    expect(create.className).not.toMatch(/opacity-50/);
  });
});

describe('AdminFilterField', () => {
  it('uses the default compact width', () => {
    render(
      <AdminFilterBar>
        <AdminFilterField>
          <input aria-label='Action' />
        </AdminFilterField>
      </AdminFilterBar>
    );

    const field = screen.getByLabelText('Action').parentElement;
    expect(field).toHaveClass('min-w-[10rem]', 'sm:basis-48');
    expect(field?.className ?? '').not.toMatch(/8\.5rem/);
  });

  it('omits the bar when every child is empty', () => {
    render(
      <AdminFilterBar>
        {false}
        {null}
      </AdminFilterBar>
    );

    expect(screen.queryByTestId('admin-filter-bar')).not.toBeInTheDocument();
  });
});

describe('AdminRecordTable', () => {
  it('renders filters left, actions left, table, then Load more', () => {
    render(
      <AdminRecordTable
        aria-label='Organizations'
        columnCount={2}
        rowCount={1}
        isLoading={false}
        hasMore
        onLoadMore={() => undefined}
        filters={
          <AdminFilterBar>
            <label>
              Name
              <input aria-label='Name' />
            </label>
          </AdminFilterBar>
        }
        actions={<AdminCreateButton label='New organization' onClick={() => undefined} />}
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            <AdminDataTableHeadCell>Status</AdminDataTableHeadCell>
          </>
        }
      >
        <tr>
          <AdminDataTableCell>Harbour Club</AdminDataTableCell>
          <AdminDataTableCell>Approved</AdminDataTableCell>
        </tr>
      </AdminRecordTable>
    );

    const card = screen.getByTestId('admin-record-table');
    const filters = screen.getByTestId('admin-filter-bar');
    const actions = screen.getByTestId('admin-record-table-actions');
    const table = screen.getByRole('table', { name: 'Organizations' });
    const loadMore = screen.getByRole('button', { name: 'Load more' });
    const create = screen.getByRole('button', { name: 'New organization' });

    expect(card).toContainElement(filters);
    expect(card).toContainElement(actions);
    expect(card).toContainElement(table);
    expect(card).toContainElement(loadMore);
    expect(following(filters, actions)).toBe(true);
    expect(following(actions, table)).toBe(true);
    expect(following(table, loadMore)).toBe(true);
    expect(actions).toHaveClass('justify-start');
    expect(actions).toContainElement(create);
    expect(screen.queryByTestId('admin-filter-bar-trailing')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });

  it('omits the actions row when there are no buttons', () => {
    render(
      <AdminRecordTable
        aria-label='Deleted'
        columnCount={1}
        rowCount={0}
        isLoading={false}
        filters={
          <AdminFilterBar>
            <label>
              Name
              <input aria-label='Name' />
            </label>
          </AdminFilterBar>
        }
        head={<AdminDataTableHeadCell>Name</AdminDataTableHeadCell>}
      >
        {null}
      </AdminRecordTable>
    );

    expect(screen.getByTestId('admin-filter-bar')).toBeVisible();
    expect(screen.queryByTestId('admin-record-table-actions')).not.toBeInTheDocument();
    expect(screen.getByText('No records match the current filters.')).toBeVisible();
  });

  it('hides the empty sentence when the list failed', () => {
    render(
      <AdminRecordTable
        aria-label='Organizations'
        columnCount={1}
        rowCount={0}
        isLoading={false}
        hasError
        head={<AdminDataTableHeadCell>Name</AdminDataTableHeadCell>}
      >
        {null}
      </AdminRecordTable>
    );

    expect(screen.queryByText('No records match the current filters.')).not.toBeInTheDocument();
  });

  it('keeps banners and Refreshing out of the card', () => {
    render(
      <AdminRecordTable
        aria-label='Users'
        columnCount={1}
        rowCount={1}
        isLoading
        head={<AdminDataTableHeadCell>Email</AdminDataTableHeadCell>}
      >
        <tr>
          <AdminDataTableCell>Ada</AdminDataTableCell>
        </tr>
      </AdminRecordTable>
    );

    const card = screen.getByTestId('admin-record-table');
    expect(card.querySelector('[role="alert"]')).toBeNull();
    const busy = screen.getByRole('status');
    expect(busy).toHaveTextContent('Refreshing...');
    expect(busy).toHaveClass('sr-only');
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

describe('ResourceTableShell banners', () => {
  it('renders the list error above the table card', () => {
    render(
      <ResourceTableShell
        ariaLabel='Users'
        rows={[]}
        getLabel={() => 'Ada'}
        middleColumnCount={1}
        hasActions={false}
        isLoading={false}
        error='Could not load users.'
        isExpanded={() => false}
        onToggle={() => undefined}
        detail={null}
        head={<AdminDataTableHeadCell>Name</AdminDataTableHeadCell>}
        renderCells={() => <AdminDataTableCell>Ada</AdminDataTableCell>}
      />
    );

    const banner = screen.getByText('Could not load users.');
    expect(screen.getByTestId('admin-record-table')).not.toContainElement(banner);
    expect(banner.parentElement?.className ?? '').not.toContain('mb-3');
    expect(screen.queryByText('No records match the current filters.')).not.toBeInTheDocument();
  });
});

describe('AdminEditorPanel', () => {
  it('omits the bar when actions is false', () => {
    render(
      <AdminEditorPanel actions={false}>
        <p>Fields</p>
      </AdminEditorPanel>
    );

    expect(screen.getByText('Fields')).toBeVisible();
    expect(screen.getByTestId('admin-editor-panel').querySelector('.border-t')).toBeNull();
  });

  it('puts the accessory at the top right, before the fields', () => {
    render(
      <AdminEditorPanel accessory={<button type='button'>Version 1 · Latest</button>}>
        <p>Fields</p>
      </AdminEditorPanel>
    );

    const panel = screen.getByTestId('admin-editor-panel');
    const accessory = screen.getByTestId('admin-editor-accessory');
    const fields = screen.getByText('Fields');
    expect(panel).toContainElement(accessory);
    expect(accessory).toContainElement(screen.getByRole('button', { name: 'Version 1 · Latest' }));
    expect(accessory.compareDocumentPosition(fields) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(accessory.className).toContain('justify-end');
  });

  it('omits the accessory row when none is passed', () => {
    render(
      <AdminEditorPanel>
        <p>Fields</p>
      </AdminEditorPanel>
    );

    expect(screen.queryByTestId('admin-editor-accessory')).not.toBeInTheDocument();
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
  it('gives grey secondary buttons the dark slate border', () => {
    render(
      <Button type='button' variant='secondary'>
        Test model
      </Button>
    );

    expect(screen.getByRole('button', { name: 'Test model' })).toHaveClass(
      'border-slate-900',
      'bg-slate-100'
    );
  });

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
