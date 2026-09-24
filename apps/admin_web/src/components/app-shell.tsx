'use client';

import { useState, useEffect, useCallback, type ReactNode } from 'react';
import Image from 'next/image';

import { LegalLinks } from './legal-links';
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

function MenuIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill='none'
      viewBox='0 0 24 24'
      strokeWidth='1.5'
      stroke='currentColor'
    >
      <path
        strokeLinecap='round'
        strokeLinejoin='round'
        d='M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5'
      />
    </svg>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill='none'
      viewBox='0 0 24 24'
      strokeWidth='1.5'
      stroke='currentColor'
    >
      <path
        strokeLinecap='round'
        strokeLinejoin='round'
        d='M6 18L18 6M6 6l12 12'
      />
    </svg>
  );
}

/**
 * Format a datetime string for display.
 * Uses the browser's timezone, falling back to UTC if unavailable.
 */
function formatLastLogin(dateStr: string | undefined): string | null {
  if (!dateStr) return null;
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return null;

    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone,
      timeZoneName: 'short',
    });
  } catch {
    return null;
  }
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
    <div className='min-h-screen'>
      {/* Header */}
      <header className='sticky top-0 z-40 border-b border-slate-200 bg-white'>
        <div className='mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 sm:px-6 sm:py-4'>
          <div className='flex items-center gap-3'>
            {/* Mobile menu button */}
            {sections.length > 0 && (
              <button
                type='button'
                onClick={() => setMobileMenuOpen(true)}
                className='rounded-md p-2 text-slate-600 hover:bg-slate-100 lg:hidden'
                aria-label='Open menu'
              >
                <MenuIcon className='h-6 w-6' />
              </button>
            )}
            <Image
              src='/images/siutindei-logo.svg'
              alt=''
              aria-hidden
              width={80}
              height={80}
              className='h-[2.2rem] w-[2.2rem] shrink-0 lg:mb-[-16px] lg:mt-[-16px] lg:h-[80px] lg:w-[80px]'
            />
            <div>
              <h1 className='text-[calc(1.125rem*0.8)] font-semibold sm:text-[calc(1.25rem*0.8)]'>
                Siu Tin Dei Admin
              </h1>
              <p className='hidden text-sm text-slate-500 sm:block'>
                {headerDescriptionText}
              </p>
              {/* Show current section on mobile */}
              {activeLabel && (
                <p className='text-sm text-slate-500 lg:hidden'>{activeLabel}</p>
              )}
            </div>
          </div>
          <div className='flex items-center gap-2 sm:gap-3'>
            {userEmail && (
              <div className='hidden text-right sm:block'>
                <span className='text-sm text-slate-600'>{userEmail}</span>
                {formattedLastLogin && (
                  <p className='text-xs text-slate-400'>
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
          className='fixed inset-0 z-50 bg-black/50 lg:hidden'
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
          <div className='flex items-center justify-between border-b border-slate-200 px-4 py-3'>
            <span className='font-semibold'>Menu</span>
            <button
              type='button'
              onClick={() => setMobileMenuOpen(false)}
              className='rounded-md p-2 text-slate-600 hover:bg-slate-100'
              aria-label='Close menu'
            >
              <CloseIcon className='h-5 w-5' />
            </button>
          </div>
          {userEmail && (
            <div className='border-b border-slate-200 px-4 py-3'>
              <p className='truncate text-sm text-slate-600'>{userEmail}</p>
              {formattedLastLogin && (
                <p className='mt-0.5 text-xs text-slate-400'>
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
                      <hr className='my-3 border-slate-200' />
                    )}
                    <button
                      type='button'
                      onClick={() => handleNavSelect(section.key)}
                      onMouseEnter={() => onIntent?.(section.key)}
                      onFocus={() => onIntent?.(section.key)}
                      className={`w-full rounded-md px-3 py-2.5 text-left text-sm font-medium ${
                        isActive
                          ? 'bg-slate-900 text-white'
                          : 'text-slate-700 hover:bg-slate-100'
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
                      <hr className='my-3 border-slate-200' />
                    )}
                    <button
                      type='button'
                      onClick={() => onSelect(section.key)}
                      onMouseEnter={() => onIntent?.(section.key)}
                      onFocus={() => onIntent?.(section.key)}
                      className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                        isActive
                          ? 'bg-slate-900 text-white'
                          : 'text-slate-700 hover:bg-slate-100'
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
        <main className='min-w-0 flex-1 space-y-4 sm:space-y-6'>{children}</main>
      </div>

      {/* Footer */}
      <footer className='border-t border-slate-200 bg-white'>
        <div className='mx-auto w-full max-w-7xl px-4 py-4 sm:px-6'>
          <LegalLinks className='text-center text-xs text-slate-500' />
        </div>
      </footer>
    </div>
  );
}
