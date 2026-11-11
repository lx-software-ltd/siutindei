import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Modal } from '@/components/shared/ui/modal';

describe('Modal', () => {
  it('inerts page content and focuses the first field in the body', () => {
    render(
      <>
        <main id="main-content">
          <button type="button">Outside</button>
        </main>
        <footer id="contact">Footer</footer>
        <Modal isOpen title="Search filters" onClose={vi.fn()}>
          <button type="button">First field</button>
          <button type="button">Second field</button>
        </Modal>
      </>,
    );

    const main = document.getElementById('main-content');
    expect(main?.hasAttribute('inert')).toBe(true);
    expect(document.getElementById('contact')?.hasAttribute('inert')).toBe(
      true,
    );
    expect(document.body.classList.contains('navbar-mobile-menu-scroll-lock'))
      .toBe(true);

    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'First field' }),
    );
  });

  it('is sized by its fixed container, not by viewport units, so the header stays on screen in iOS Safari', () => {
    render(
      <Modal isOpen title="Search activities" onClose={vi.fn()}>
        <button type="button">Field</button>
      </Modal>,
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-h-full', 'min-w-0', 'w-full');
    expect(dialog.className).toContain('max-w-[min(100%,42rem)]');
    expect(dialog.className).toContain('[contain:inline-size]');
    expect(dialog.className).not.toMatch(/max-h-\[\d+d?vh\]/);
    expect(dialog.parentElement).toHaveClass('fixed', 'inset-0', 'overflow-x-hidden');
    expect(
      screen.getByRole('heading', { name: 'Search activities' }).parentElement,
    ).toHaveClass('shrink-0');
  });

  it('keeps the body from scrolling sideways', () => {
    render(
      <Modal isOpen title="Search activities" onClose={vi.fn()}>
        <button type="button">Field</button>
      </Modal>,
    );

    expect(document.querySelector('[data-modal-body]')).toHaveClass(
      'overflow-x-hidden',
      'overflow-y-auto',
    );
  });

  it('renders footer actions outside the scrolling body', () => {
    render(
      <Modal
        isOpen
        title="Search activities"
        onClose={vi.fn()}
        footer={<button type="button">Search</button>}
      >
        <button type="button">Field</button>
      </Modal>,
    );

    const action = screen.getByRole('button', { name: 'Search' });
    expect(action.closest('[data-modal-body]')).toBeNull();
    expect(action.closest('[data-modal-footer]')).toHaveClass('shrink-0');
    expect(screen.getByRole('dialog').contains(action)).toBe(true);
    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'Field' }),
    );
  });

  it('stays clickable when opened from inside main content', () => {
    const onClose = vi.fn();
    render(
      <main id="main-content">
        <Modal isOpen title="Navigator" onClose={onClose}>
          <button type="button">Tile</button>
        </Modal>
      </main>,
    );

    const tile = screen.getByRole('button', { name: 'Tile' });
    expect(tile.closest('[inert]')).toBeNull();
    fireEvent.click(tile);
    expect(onClose).not.toHaveBeenCalled();
  });
});
