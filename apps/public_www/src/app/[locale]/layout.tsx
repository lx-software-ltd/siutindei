import type { ReactNode } from 'react';

import { PageLayout } from '@/components/shared/page-layout';
import { WhatsappFab } from '@/components/shared/whatsapp-fab';
import {
  generateLocaleStaticParams,
  type LocaleRouteParams,
  resolveLocalePageContext,
} from '@/lib/locale-page';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';
import { resolvePublicSiteConfig } from '@/lib/site-config';

interface LocaleLayoutProps {
  readonly children: ReactNode;
  readonly params: LocaleRouteParams;
}

export function generateStaticParams() {
  return generateLocaleStaticParams();
}

export default async function LocaleLayout({
  children,
  params,
}: LocaleLayoutProps) {
  const { locale, content } = await resolveLocalePageContext(params);
  const direction = content.meta.direction === 'rtl' ? 'rtl' : 'ltr';
  const publicSiteConfig = resolvePublicSiteConfig();
  const noscriptCopy = content.common.shell.noscript;
  const localizedHomeHref = localizePath(ROUTES.home, locale);
  const localizedContactHref = `${localizePath(ROUTES.home, locale)}#contact`;

  return (
    <div data-locale={locale} dir={direction}>
      <noscript>
        <section className="mx-auto mt-4 max-w-3xl rounded-xl border border-black/10 bg-white px-4 py-4 text-sm text-black/80">
          <p className="font-semibold text-black">{noscriptCopy.title}</p>
          <p className="mt-2">{noscriptCopy.description}</p>
          <p className="mt-3 flex flex-wrap gap-4">
            <a
              href={localizedHomeHref}
              className="font-semibold underline underline-offset-4"
            >
              {noscriptCopy.homeLabel}
            </a>
            <a
              href={localizedContactHref}
              className="font-semibold underline underline-offset-4"
            >
              {noscriptCopy.contactLabel}
            </a>
          </p>
        </section>
      </noscript>
      <PageLayout
        locale={locale}
        navbarContent={content.navbar}
        footerContent={content.footer}
      >
        {children}
      </PageLayout>
      {publicSiteConfig.whatsappUrl ? (
        <WhatsappFab label={content.common.shell.whatsappFabLabel} />
      ) : null}
    </div>
  );
}
