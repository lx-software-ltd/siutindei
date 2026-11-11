'use client';

import type { ReactNode } from 'react';
import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

import {
  getFocusableElements,
  handleFocusTrapKeyDown,
  setInertOnElements,
} from '@/lib/focus-management';

interface ModalProps {
  readonly isOpen: boolean;
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
  /**
   * Actions that stay in view under the scrolling body. Landscape phones
   * are too short for a pinned bar, so there it scrolls with the body.
   */
  readonly footer?: ReactNode;
}

const SCROLL_LOCK_CLASS = 'navbar-mobile-menu-scroll-lock';
const INERT_TARGET_IDS = ['main-content', 'contact'] as const;

export function Modal({
  isOpen,
  title,
  onClose,
  children,
  footer,
}: ModalProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    triggerRef.current = document.activeElement;

    const hadScrollLock = document.body.classList.contains(SCROLL_LOCK_CLASS);
    document.body.classList.add(SCROLL_LOCK_CLASS);
    const releaseInert = setInertOnElements(INERT_TARGET_IDS, true);

    const contentRoot = panelRef.current?.querySelector<HTMLElement>(
      '[data-modal-body]',
    );
    const focusTarget = contentRoot
      ? getFocusableElements(contentRoot)[0]
      : panelRef.current
        ? getFocusableElements(panelRef.current)[0]
        : undefined;
    focusTarget?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
        return;
      }

      if (panelRef.current) {
        handleFocusTrapKeyDown(event, panelRef.current);
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      if (!hadScrollLock) {
        document.body.classList.remove(SCROLL_LOCK_CLASS);
      }
      releaseInert();
      document.removeEventListener('keydown', handleKeyDown);
      if (triggerRef.current instanceof HTMLElement) {
        triggerRef.current.focus();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen || typeof document === 'undefined') {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center pt-10 sm:items-center sm:p-4">
      <button
        type="button"
        className="absolute inset-0 bg-ink-900/40"
        aria-label="Close dialog"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 flex max-h-full w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl sm:rounded-2xl"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-brand-100 px-4 py-3 short:py-1">
          <h2 id={titleId} className="text-base font-semibold text-ink-900">
            {title}
          </h2>
          <button
            type="button"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full text-ink-700 hover:bg-brand-50"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="flex min-h-0 flex-col short:block short:overflow-x-hidden short:overflow-y-auto short:overscroll-contain">
          <div
            data-modal-body
            className="min-h-0 overflow-y-auto overflow-x-hidden overscroll-contain px-4 py-4 short:overflow-visible"
          >
            {children}
          </div>
          {footer ? (
            <div
              data-modal-footer
              className="shrink-0 border-t border-brand-100 px-4 py-3 short:border-t-0 short:pt-0"
            >
              {footer}
            </div>
          ) : null}
        </div>
      </div>
    </div>,
    document.body,
  );
}
