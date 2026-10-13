import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { WorkspaceEmpty, WorkspaceScopeGate } from '@/components/admin/workspace-empty';

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NuqsTestingAdapter hasMemory searchParams='?section=locations'>
      {children}
    </NuqsTestingAdapter>
  );
}

describe('WorkspaceEmpty', () => {
  it('renders the choose prompt as an input card', async () => {
    const user = userEvent.setup();
    render(<WorkspaceEmpty noun='locations' />, { wrapper });

    const heading = screen.getByRole('heading', { name: 'Choose an organization' });
    expect(heading.closest('section')).toBeTruthy();
    expect(
      screen.getByText('Open an organization from the catalog to work on locations.')
    ).toBeVisible();
    expect(screen.getByTestId('admin-editor-panel')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Open catalog' }));
  });
});

describe('WorkspaceScopeGate', () => {
  it('shows the manager empty card when no organization is open', () => {
    render(
      <WorkspaceScopeGate orgId={null} isAdmin={false} noun='locations'>
        <p>Locations table</p>
      </WorkspaceScopeGate>,
      { wrapper }
    );

    expect(
      screen.getByRole('heading', { name: 'No organization is selected' })
    ).toBeVisible();
    expect(screen.queryByText('Locations table')).not.toBeInTheDocument();
  });
});
