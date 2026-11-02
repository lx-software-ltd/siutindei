'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { isValidLocale, type Locale } from '@/content/locales';
import type { NavbarContent } from '@/content/types';
import { localizeHref, normalizeLocalizedPath } from '@/lib/locale-routing';

const LANGUAGE_FLAG_SRC = {
  en: '/images/flags/uk.svg',
  'zh-HK': '/images/flags/hong-kong.svg',
} as const satisfies Record<Locale, string>;

interface NavbarLanguageSwitcherProps {
  readonly locale: Locale;
  readonly content: NavbarContent;
}

export function NavbarLanguageSwitcher({
  locale,
  content,
}: NavbarLanguageSwitcherProps) {
  const pathname = usePathname();
  const currentPath = normalizeLocalizedPath(pathname ?? '/');

  return (
    <nav
      className="flex items-center gap-1"
      aria-label={content.languageSelector.menuAriaLabel}
    >
      {content.languageSelector.options.map((option) => {
        if (!isValidLocale(option.locale)) {
          return null;
        }

        const isCurrent = option.locale === locale;

        return (
          <Link
            key={option.locale}
            href={localizeHref(currentPath, option.locale)}
            className={`link-unadorned inline-flex h-11 w-11 items-center justify-center rounded-full ${
              isCurrent
                ? 'bg-brand-50 ring-2 ring-brand-500 ring-offset-2'
                : 'hover:bg-brand-50'
            }`}
            aria-label={option.label}
            aria-current={isCurrent ? 'page' : undefined}
            title={option.label}
          >
            <img
              src={LANGUAGE_FLAG_SRC[option.locale]}
              alt=""
              width={28}
              height={28}
              decoding="async"
              className="h-7 w-7 rounded-full object-cover ring-1 ring-ink-900/15"
            />
          </Link>
        );
      })}
    </nav>
  );
}
