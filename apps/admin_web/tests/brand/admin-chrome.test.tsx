import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import AdminLoading from '@/app/admin/loading';
import { LegalLinks } from '@/components/legal-links';
import { LoginFooter } from '@/components/login/login-footer';
import { StatusBanner } from '@/components/status-banner';
import { AdminTabStrip } from '@/components/ui/admin-tab-strip';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { LanguageToggleInput } from '@/components/ui/language-toggle-input';
import { StatusBadge } from '@/components/ui/status-badge';

describe('console brand corrections', () => {
  it('keeps the neutral badge grey', () => {
    render(
      <>
        <StatusBadge status='hidden' />
        <StatusBadge status='you' label='You' />
      </>
    );

    for (const badge of [screen.getByText('hidden'), screen.getByText('You')]) {
      expect(badge).toHaveClass('bg-slate-200', 'text-slate-700');
      expect(badge).not.toHaveClass('bg-brand-100', 'bg-yellow-100');
    }
  });

  it('separates info banners from pending review', () => {
    render(
      <>
        <StatusBanner kind='info'>Loaded</StatusBanner>
        <StatusBanner kind='pending-review'>Waiting</StatusBanner>
      </>
    );

    expect(screen.getByText('Loaded').closest('div')).toHaveClass(
      'bg-white',
      'border-brand-200'
    );
    expect(screen.getByText('Loaded').closest('div')).not.toHaveClass('bg-brand-50');
    expect(screen.getByText('Waiting').closest('div')).toHaveClass(
      'bg-blue-50',
      'text-blue-900'
    );
  });

  it('loads the admin route with the bao notice instead of the login backdrop', () => {
    render(<AdminLoading />);

    expect(screen.getByRole('status')).toHaveTextContent(
      'Preparing your admin session…'
    );
    expect(screen.getByRole('status')).not.toHaveClass('bg-white');
    expect(document.querySelector('img.admin-login-bao')).toHaveAttribute(
      'src',
      '/images/small-world/bubble-bao.webp'
    );
    expect(screen.queryByText('Loading admin workspace...')).not.toBeInTheDocument();
    expect(document.querySelector('.admin-login-hero')).toBeNull();
  });

  it('ranks yellow, cream, white, ink, and a grey disabled primary', () => {
    render(
      <>
        <Button type='button'>New organization</Button>
        <Button type='button' disabled>
          Approve
        </Button>
        <Button type='button' variant='secondary'>
          Apply
        </Button>
        <Button type='button' variant='outline'>
          Log out
        </Button>
        <Button type='button' variant='ink'>
          Commit
        </Button>
      </>
    );

    const create = screen.getByRole('button', { name: 'New organization' });
    const approve = screen.getByRole('button', { name: 'Approve' });
    expect(create).toHaveClass('bg-accent-500', 'text-ink-900');
    expect(approve).toHaveClass('disabled:bg-slate-100', 'disabled:text-slate-600');
    expect(screen.getByRole('button', { name: 'Apply' })).toHaveClass('bg-brand-100');
    expect(screen.getByRole('button', { name: 'Apply' })).not.toHaveClass('bg-white');
    expect(screen.getByRole('button', { name: 'Log out' })).toHaveClass('bg-white');
    expect(screen.getByRole('button', { name: 'Log out' })).not.toHaveClass('bg-brand-100');
    expect(screen.getByRole('button', { name: 'Commit' })).toHaveClass(
      'bg-ink-900',
      'text-white'
    );
  });

  it('confirms with ink and cancels with the filled secondary', () => {
    render(
      <ConfirmDialog
        open
        title='Discard unsaved changes?'
        message='The open record has edits that have not been saved.'
        confirmLabel='Discard changes'
        onConfirm={() => undefined}
        onCancel={() => undefined}
      />
    );

    expect(screen.getByRole('button', { name: 'Discard changes' })).toHaveClass('bg-ink-900');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass('bg-brand-100');
  });

  it('gives the tab track a white surface on the cream page', () => {
    render(
      <AdminTabStrip
        aria-label='Catalog views'
        items={[
          { key: 'table', label: 'Table' },
          { key: 'map', label: 'Map' },
        ]}
        activeKey='table'
        onChange={() => undefined}
      />
    );

    expect(screen.getByRole('group', { name: 'Catalog views' })).toHaveClass(
      'border',
      'border-brand-200',
      'bg-white'
    );
  });

  it('marks the active language with an ink ring', () => {
    render(
      <LanguageToggleInput
        id='org-name'
        label='Name'
        values={{ en: 'Harbour', zh: '', yue: '' }}
        onChange={() => undefined}
      />
    );

    const active = screen.getByRole('button', { name: 'Select English (en)' });
    expect(active).toHaveClass('ring-ink-900');
    expect(active).not.toHaveClass('ring-brand-200', 'border-brand-500');
    expect(screen.getByText('Name')).toHaveClass('mb-1');
  });

  it('opens the public site in a new tab and darkens legal hover', () => {
    render(
      <>
        <LoginFooter />
        <LegalLinks />
      </>
    );

    const links = screen.getAllByRole('link', { name: 'Go to siutindei.com' });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute('target', '_blank');
    expect(links[0]?.getAttribute('rel')).toContain('noopener');
    expect(screen.getAllByRole('link', { name: 'Privacy Policy' })[0]).toHaveClass(
      'hover:text-brand-700'
    );
  });
});
