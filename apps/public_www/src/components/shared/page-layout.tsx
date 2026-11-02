import type { ReactNode } from 'react';

import type { Locale } from '@/content/locales';
import type { FooterContent, NavbarContent } from '@/content/types';
import { Footer } from '@/components/sections/footer';
import { Navbar } from '@/components/sections/navbar';
import { SearchProvider } from '@/components/shared/search/search-context';

interface PageLayoutProps {
  readonly locale: Locale;
  readonly navbarContent: NavbarContent;
  readonly footerContent: FooterContent;
  readonly children: ReactNode;
  readonly mainClassName?: string;
  readonly mainId?: string;
}

const DEFAULT_MAIN_CLASSNAME = 'min-h-screen flex-1 bg-white';

export function PageLayout({
  locale,
  navbarContent,
  footerContent,
  children,
  mainClassName,
  mainId = 'main-content',
}: PageLayoutProps) {
  return (
    <SearchProvider>
      <div className="flex min-h-screen flex-col">
        <Navbar locale={locale} content={navbarContent} />
        <main
          id={mainId}
          tabIndex={-1}
          className={mainClassName ?? DEFAULT_MAIN_CLASSNAME}
        >
          {children}
        </main>
        <Footer locale={locale} content={footerContent} />
      </div>
    </SearchProvider>
  );
}
