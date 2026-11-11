'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import type { Locale } from '@/content/locales';
import type { NavbarContent } from '@/content/types';
import { SearchBarCompact } from '@/components/sections/search/search-bar-compact';
import { SearchPanel } from '@/components/sections/search/search-panel';
import { useHomeHeaderReveal } from '@/lib/home-header-reveal';
import { localizeHref, localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

import { NavbarLanguageSwitcher } from './navbar-language-switcher';

interface NavbarProps {
  readonly locale: Locale;
  readonly content: NavbarContent;
}

const SHARED_HEADER_CHROME =
  'z-40 border-b border-brand-100 bg-white/95 backdrop-blur';

export function Navbar({ locale, content }: NavbarProps) {
  const pathname = usePathname();
  const isHome =
    pathname === localizePath(ROUTES.home, locale) ||
    pathname === `/${locale}` ||
    pathname === `/${locale}/`;
  const isRevealed = useHomeHeaderReveal(isHome);
  const isHomeHidden = isHome && !isRevealed;
  const headerClassName = isHome
    ? [
        'site-header--home-reveal',
        SHARED_HEADER_CHROME,
        isRevealed ? 'is-revealed' : '',
      ]
        .filter(Boolean)
        .join(' ')
    : `sticky top-0 short:static ${SHARED_HEADER_CHROME}`;

  return (
    <>
      <header
        className={headerClassName}
        aria-hidden={isHomeHidden ? true : undefined}
        inert={isHomeHidden}
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex min-h-16 items-center gap-3 py-3">
            <Link
              href={localizeHref(ROUTES.home, locale)}
              className="link-unadorned brand-title flex shrink-0 items-center gap-2 text-base font-bold text-brand-700 sm:text-lg"
            >
              <img
                src="/images/brand/siutindei-logo-mark.svg"
                alt=""
                width={38}
                height={38}
                aria-hidden="true"
                className="h-9 w-9 sm:h-10 sm:w-10"
              />
              <img
                src="/images/brand/siutindei-wordmark.svg"
                alt={content.brand}
                width={180}
                height={30}
                className="h-6 w-auto sm:h-7"
              />
            </Link>
            <div className="hidden flex-1 justify-center md:flex">
              <SearchBarCompact locale={locale} labels={content.searchBar} />
            </div>
            <div className="ml-auto flex items-center gap-2">
              <NavbarLanguageSwitcher locale={locale} content={content} />
            </div>
          </div>
          <div className="pb-3 md:hidden">
            <SearchBarCompact locale={locale} labels={content.searchBar} />
          </div>
        </div>
      </header>
      <SearchPanel locale={locale} copy={content.searchPanel} />
      {isHome ? null : (
        <div className="border-b border-brand-100 bg-white md:hidden" />
      )}
    </>
  );
}
