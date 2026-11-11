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

  it('caps its height to the visible viewport so the header stays on screen in iOS Safari', () => {
    render(
      <Modal isOpen title="Search activities" onClose={vi.fn()}>
        <button type="button">Field</button>
      </Modal>,
    );

    expect(screen.getByRole('dialog')).toHaveClass('max-h-[92dvh]');
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
