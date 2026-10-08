import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { AdminField } from '@/components/ui/admin-field-grid';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { StatusBadge } from '@/components/ui/status-badge';

describe('AdminField', () => {
  it('renders one required mark and the field error', () => {
    render(
      <AdminField label='Name' htmlFor='name' required error='Name is required'>
        <input id='name' />
      </AdminField>
    );

    expect(screen.getByText('*')).toHaveClass('text-red-600');
    expect(screen.getByRole('alert')).toHaveTextContent('Name is required');
  });
});

describe('StatusBadge', () => {
  it('uses the shared tone palette when a tone is passed', () => {
    render(<StatusBadge status='access_request' tone='blue' label='Access Request' />);

    const badge = screen.getByText('Access Request');
    expect(badge).toHaveClass('bg-blue-100');
    expect(badge).toHaveClass('text-blue-800');
  });
});

describe('ConfirmDialog', () => {
  it('uses the shared dialog shell and returns focus on close', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    const trigger = document.createElement('button');
    trigger.textContent = 'Open';
    document.body.append(trigger);
    trigger.focus();

    render(
      <ConfirmDialog
        open
        title='Discard unsaved changes?'
        message='The open record has edits that have not been saved.'
        confirmLabel='Discard changes'
        onConfirm={() => undefined}
        onCancel={onCancel}
      />
    );

    expect(screen.getByRole('alertdialog', { name: 'Discard unsaved changes?' })).toBeVisible();
    expect(document.querySelector('.bg-slate-900\\/45')).not.toBeNull();
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledOnce();
    trigger.remove();
  });
});
