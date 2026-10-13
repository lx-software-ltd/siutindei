import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { WorkspaceEmpty, WorkspaceScopeGate } from '@/components/admin/workspace-empty';

const urlUpdates: string[] = [];

function wrapper({ children }: { children: ReactNode }) {
  return (
    <NuqsTestingAdapter
      hasMemory
      searchParams='?section=locations'
      onUrlUpdate={(event) => {
        urlUpdates.push(event.queryString);
      }}
    >
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
    expect(screen.getByTestId('admin-input-card-bar')).toContainElement(
      screen.getByRole('button', { name: 'Open catalog' })
    );

    urlUpdates.length = 0;
    await user.click(screen.getByRole('button', { name: 'Open catalog' }));
    expect(urlUpdates.at(-1)).toContain('section=catalog');
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
    expect(screen.queryByTestId('admin-input-card-bar')).not.toBeInTheDocument();
    expect(screen.queryByText('Locations table')).not.toBeInTheDocument();
  });
});
