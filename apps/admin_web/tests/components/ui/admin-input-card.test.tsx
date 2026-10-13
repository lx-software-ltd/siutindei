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
      'border-slate-200',
      'bg-white',
      'shadow-sm'
    );
    expect(screen.getByText('Open an organization from the catalog.')).toBeVisible();
    expect(screen.getByText('Card body')).toBeVisible();
    const bar = screen.getByTestId('admin-input-card-bar');
    expect(bar).toHaveClass('border-t', 'border-slate-200', 'pt-4');
    expect(bar).toContainElement(screen.getByRole('button', { name: 'Open catalog' }));
  });

  it('always renders the bar when there are no actions', () => {
    render(
      <AdminInputCard title='Your request details'>
        <p>Ticket body</p>
      </AdminInputCard>
    );

    expect(screen.getByRole('heading', { name: 'Your request details' })).toBeVisible();
    const bar = screen.getByTestId('admin-input-card-bar');
    expect(bar).toBeInTheDocument();
    expect(bar.querySelector('button')).toBeNull();
  });

  it('keeps badges in the title slot without changing the heading class', () => {
    render(
      <AdminInputCard
        title='Harbour Club'
        titleAccessory={<span>operational</span>}
        actions={<Button type='button'>Update</Button>}
      >
        <p>Fields</p>
      </AdminInputCard>
    );

    const heading = screen.getByRole('heading', { name: 'Harbour Club' });
    expect(heading).toHaveClass('text-base', 'font-semibold', 'sm:text-lg');
    expect(heading.parentElement).toHaveTextContent('operational');
  });
});
