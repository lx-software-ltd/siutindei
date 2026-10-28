import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AdminInputCard } from '@/components/ui/admin-input-card';
import { Button } from '@/components/ui/button';

describe('AdminInputCard', () => {
  it('renders title, content, and a bar with the same card chrome', () => {
    render(
      <AdminInputCard
        title='Choose an organization'
        description='Open an organization from the catalog.'
        actions={<Button type='button'>Open catalog</Button>}
      >
        <p>Card body</p>
      </AdminInputCard>
    );

    const heading = screen.getByRole('heading', { name: 'Choose an organization' });
    expect(heading).toHaveClass('text-base', 'font-semibold', 'sm:text-lg');
    const card = heading.closest('section');
    expect(card).toHaveClass(
      'rounded-lg',
      'border',
      'border-brand-100',
      'bg-white',
      'shadow-sm'
    );
    expect(screen.getByText('Open an organization from the catalog.')).toBeVisible();
    expect(screen.getByText('Card body')).toBeVisible();
    const bar = screen.getByTestId('admin-input-card-bar');
    expect(bar).toHaveClass('border-t', 'border-brand-100', 'pt-4');
    expect(bar).toContainElement(screen.getByRole('button', { name: 'Open catalog' }));
  });

  it('omits the bar when there are no actions', () => {
    render(
      <AdminInputCard title='Your request details'>
        <p>Ticket body</p>
      </AdminInputCard>
    );

    expect(screen.getByRole('heading', { name: 'Your request details' })).toBeVisible();
    expect(screen.getByText('Ticket body')).toBeVisible();
    expect(screen.queryByTestId('admin-input-card-bar')).not.toBeInTheDocument();
  });

  it('shows a status banner without an empty bar', () => {
    render(
      <AdminInputCard title='Suggestion settings' status={<p>Settings failed.</p>} />
    );

    expect(screen.getByText('Settings failed.')).toBeVisible();
    expect(screen.queryByTestId('admin-input-card-bar')).not.toBeInTheDocument();
  });

  it('uses an h3 when the card sits under the page heading', () => {
    render(<AdminInputCard title='Rules' titleLevel='h3' />);

    expect(screen.getByRole('heading', { name: 'Rules', level: 3 })).toBeVisible();
  });

  it('renders a footer after the action bar', () => {
    render(
      <AdminInputCard
        title='Imports'
        actions={<Button type='button'>Upload & Import</Button>}
        footer={<p>Summary</p>}
      />
    );

    const bar = screen.getByTestId('admin-input-card-bar');
    const summary = screen.getByText('Summary');
    expect(bar.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('aligns the title accessory to the right of the heading', () => {
    render(
      <AdminInputCard
        title='Details'
        titleAccessory={<span>Version 2 · Latest</span>}
        actions={<Button type='button'>Update</Button>}
      >
        <p>Fields</p>
      </AdminInputCard>
    );

    const heading = screen.getByRole('heading', { name: 'Details' });
    expect(heading).toHaveClass('text-base', 'font-semibold', 'sm:text-lg');
    expect(heading.parentElement).toHaveTextContent('Version 2 · Latest');
    const accessory = screen.getByTestId('admin-card-title-accessory');
    expect(accessory).toHaveClass('ml-auto');
    expect(accessory).toHaveTextContent('Version 2 · Latest');
  });
});
