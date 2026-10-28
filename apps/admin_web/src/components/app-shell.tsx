'use client';

import { useState, useEffect, useCallback, type ReactNode } from 'react';
import Image from 'next/image';

import { formatDateTime } from '@/lib/date-utils';

import { CloseIcon, MenuIcon } from './icons/action-icons';
import { LegalLinks } from './legal-links';
import { PublicSiteLink } from './public-site-link';
import { Button } from './ui/button';

export interface NavSection {
  key: string;
  label: string;
  dividerBefore?: boolean;
}

export interface AppShellProps {
  sections: NavSection[];
  activeKey: string;
  onSelect: (key: string) => void;
  /** Hover or focus on a nav item. Used to prefetch that section's list. */
  onIntent?: (key: string) => void;
  onLogout: () => void;
  userEmail?: string;
  lastAuthTime?: string;
  headerDescription?: string;
  children: ReactNode;
}

function formatLastLogin(dateStr: string | undefined): string | null {
  if (!dateStr) {
    return null;
  }
  const formatted = formatDateTime(dateStr);
  return formatted === '—' ? null : formatted;
}

export function AppShell({
  sections,
  activeKey,
  onSelect,
  onIntent,
  onLogout,
  userEmail,
  lastAuthTime,
  headerDescription,
  children,
}: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const formattedLastLogin = formatLastLogin(lastAuthTime);
  const headerDescriptionText =
    headerDescription ?? 'Manage organizations, activities, and schedules.';

  // Close mobile menu on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileMenuOpen]);

  const handleNavSelect = useCallback(
    (key: string) => {
      onSelect(key);
      setMobileMenuOpen(false);
    },
    [onSelect]
  );

  const activeLabel = sections.find((s) => s.key === activeKey)?.label;

  return (
    <div className='admin-focus min-h-screen'>
      {/* Header */}
      <header className='sticky top-0 z-40 border-b border-brand-100 bg-white/95 backdrop-blur'>
        <div className='mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 sm:px-6 sm:py-4'>
          <div className='flex items-center gap-3'>
            {/* Mobile menu button */}
            {sections.length > 0 && (
              <button
                type='button'
                onClick={() => setMobileMenuOpen(true)}
                className='rounded-md p-2 text-ink-700 hover:bg-brand-50 lg:hidden'
                aria-label='Open menu'
              >
                <MenuIcon className='h-6 w-6' />
              </button>
            )}
            <Image
              src='/images/siutindei-logo.svg'
              alt=''
              aria-hidden
              width={64}
              height={64}
              className='h-[1.76rem] w-[1.76rem] shrink-0 lg:mb-[-8px] lg:mt-[-8px] lg:h-[64px] lg:w-[64px]'
            />
            <div>
              <div className='flex items-center gap-2'>
                <h1 className='brand-title text-[calc(1.125rem*0.8)] font-semibold text-brand-700 sm:text-[calc(1.25rem*0.8)]'>
                  Siu Tin Dei
                </h1>
                <p className='hidden rounded-full bg-ink-900 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-brand-100 sm:inline-flex'>
                  Admin console
                </p>
              </div>
              <p className='hidden text-sm text-ink-700 sm:block'>
                {headerDescriptionText}
              </p>
              {activeLabel && (
                <p className='text-sm text-ink-500 lg:hidden'>{activeLabel}</p>
              )}
            </div>
          </div>
          <div className='flex items-center gap-2 sm:gap-3'>
            {userEmail && (
              <div className='hidden text-right sm:block'>
                <span className='text-sm text-ink-700'>{userEmail}</span>
                {formattedLastLogin && (
                  <p className='text-xs text-ink-500'>
                    Last login: {formattedLastLogin}
                  </p>
                )}
              </div>
            )}
            <Button type='button' variant='outline' onClick={onLogout}>
              <span className='hidden sm:inline'>Log out</span>
              <span className='sm:hidden'>Exit</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Mobile navigation overlay */}
      {mobileMenuOpen && (
        <div
          className='fixed inset-0 z-50 bg-ink-900/50 lg:hidden'
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden='true'
        />
      )}

      {/* Mobile navigation drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-72 transform bg-white shadow-xl transition-transform duration-300 ease-in-out lg:hidden ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className='flex h-full flex-col'>
          <div className='flex items-center justify-between border-b border-brand-100 px-4 py-3'>
            <span className='font-semibold text-ink-900'>Menu</span>
            <button
              type='button'
              onClick={() => setMobileMenuOpen(false)}
              className='rounded-md p-2 text-ink-700 hover:bg-brand-50'
              aria-label='Close menu'
            >
              <CloseIcon className='h-5 w-5' />
            </button>
          </div>
          {userEmail && (
            <div className='border-b border-brand-100 px-4 py-3'>
              <p className='truncate text-sm text-ink-700'>{userEmail}</p>
              {formattedLastLogin && (
                <p className='mt-0.5 text-xs text-ink-500'>
                  Last login: {formattedLastLogin}
                </p>
              )}
            </div>
          )}
          <nav className='flex-1 overflow-y-auto p-4'>
            <div className='space-y-1'>
              {sections.map((section) => {
                const isActive = section.key === activeKey;
                return (
                  <div key={section.key}>
                    {section.dividerBefore && (
                      <hr className='my-3 border-brand-100' />
                    )}
                    <button
                      type='button'
                      onClick={() => handleNavSelect(section.key)}
                      onMouseEnter={() => onIntent?.(section.key)}
                      onFocus={() => onIntent?.(section.key)}
                      className={`w-full rounded-md px-3 py-2.5 text-left text-sm font-medium ${
                        isActive
                          ? 'bg-ink-900 font-semibold text-white'
                          : 'text-ink-700 hover:bg-brand-50'
                      }`}
                    >
                      {section.label}
                    </button>
                  </div>
                );
              })}
            </div>
          </nav>
        </div>
      </aside>

      {/* Main content area */}
      <div className='mx-auto flex w-full max-w-7xl gap-6 px-4 py-4 sm:px-6 sm:py-6'>
        {/* Desktop sidebar */}
        {sections.length > 0 && (
          <aside className='hidden w-56 shrink-0 lg:block'>
            <nav className='sticky top-20 space-y-1'>
              {sections.map((section) => {
                const isActive = section.key === activeKey;
                return (
                  <div key={section.key}>
                    {section.dividerBefore && (
                      <hr className='my-3 border-brand-100' />
                    )}
                    <button
                      type='button'
                      onClick={() => onSelect(section.key)}
                      onMouseEnter={() => onIntent?.(section.key)}
                      onFocus={() => onIntent?.(section.key)}
                      className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                        isActive
                          ? 'bg-ink-900 font-semibold text-white'
                          : 'text-ink-700 hover:bg-brand-50'
                      }`}
                    >
                      {section.label}
                    </button>
                  </div>
                );
              })}
            </nav>
          </aside>
        )}
        <main className='min-w-0 flex-1 space-y-4'>{children}</main>
      </div>

      {/* Footer */}
      <footer className='border-t border-brand-100 bg-brand-50'>
        <div className='mx-auto flex w-full max-w-7xl flex-col items-center gap-3 px-4 py-4 text-center text-xs text-ink-700 sm:flex-row sm:justify-between sm:px-6 sm:text-left'>
          <p>
            Looking for the public site? <PublicSiteLink />
          </p>
          <LegalLinks className='whitespace-nowrap text-xs text-ink-700' />
        </div>
      </footer>
    </div>
  );
}
