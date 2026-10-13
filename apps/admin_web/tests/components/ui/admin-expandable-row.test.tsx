import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DeleteIcon } from '@/components/icons/action-icons';
import { AdminDataTableCell } from '@/components/ui/admin-data-table';
import { AdminExpandableRow } from '@/components/ui/admin-expandable-row';
import { AdminRowActions } from '@/components/ui/admin-row-actions';

function renderRow(onToggle: () => void, onDelete = vi.fn()) {
  return render(
    <table>
      <tbody>
        <AdminExpandableRow
          id='row-1'
          label='Example row'
          expanded={false}
          onToggle={onToggle}
          columnCount={3}
          cells={<AdminDataTableCell>Example</AdminDataTableCell>}
          actions={
            <AdminRowActions
              actions={[
                {
                  key: 'delete',
                  label: 'Delete',
                  tone: 'danger',
                  icon: <DeleteIcon className='h-4 w-4' />,
                  onClick: onDelete,
                },
              ]}
            />
          }
          detail={<p>Detail</p>}
        />
      </tbody>
    </table>
  );
}

describe('AdminExpandableRow', () => {
  it('expands when the operations cell padding is clicked', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    renderRow(onToggle);

    const row = screen.getByTestId('admin-row-row-1');
    const operationsCell = row.querySelector('td:last-child');
    expect(operationsCell).toBeTruthy();
    await user.click(operationsCell as HTMLElement);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('does not expand when an operations button is clicked', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    const onDelete = vi.fn();
    renderRow(onToggle, onDelete);

    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onToggle).not.toHaveBeenCalled();
  });
});
