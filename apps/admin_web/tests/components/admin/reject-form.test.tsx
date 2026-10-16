import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { RejectForm } from '@/components/admin/org-review/reject-form';

describe('RejectForm', () => {
  it('starts with hide checked and reports the chosen reason', async () => {
    const user = userEvent.setup();
    const onReason = vi.fn();
    render(
      <RejectForm
        reason=''
        notes=''
        hideListing
        onReason={onReason}
        onNotes={vi.fn()}
        onHideListing={vi.fn()}
      />
    );

    expect(screen.getByLabelText('Hide from public listing')).toBeChecked();
    await user.selectOptions(screen.getByLabelText(/Reject reason/), 'poor_data');
    expect(onReason).toHaveBeenCalledWith('poor_data');
  });
});