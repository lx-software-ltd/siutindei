import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PendingRequestNotice } from '@/components/admin/pending-request-notice';
import type { Ticket } from '@/lib/api-client-user';

const request = {
  id: 't-1',
  ticket_id: 'TCK-100',
  ticket_type: 'access_request',
  organization_name: 'Harbour Club',
  message: 'Please add this listing.',
  status: 'pending',
  submitter_email: 'desk@example.com',
  submitter_id: 'user-1',
  created_at: '2024-02-01T00:00:00Z',
  reviewed_at: null,
  reviewed_by: null,
} as Ticket;

describe('PendingRequestNotice', () => {
  it('renders the pending ticket as an input card', () => {
    render(<PendingRequestNotice request={request} />);

    const heading = screen.getByRole('heading', { name: 'Your request details' });
    expect(heading.closest('section')).toBeTruthy();
    expect(heading).toHaveClass('text-base', 'font-semibold', 'sm:text-lg');
    expect(screen.getByTestId('admin-input-card-bar')).toBeInTheDocument();
    expect(screen.getByText('TCK-100')).toBeVisible();
    expect(screen.getByText('Harbour Club')).toBeVisible();
    expect(screen.getByText('Please add this listing.')).toBeVisible();
  });
});
