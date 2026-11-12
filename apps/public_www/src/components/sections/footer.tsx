import Link from 'next/link';

import type { Locale } from '@/content/locales';
import type { FooterContent } from '@/content/types';
import { formatContentTemplate } from '@/content/content-field-utils';
import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { localizeHref } from '@/lib/locale-routing';
import { getCopyrightYear, getSiteConfig } from '@/lib/site-config';

interface FooterProps {
  readonly locale: Locale;
  readonly content: FooterContent;
}

/** Phones stack the links tightly, so each one pads out its own tap area. */
const FOOTER_LINK_CLASS = 'inline-block py-1.5 md:inline md:py-0';

export function Footer({ locale, content }: FooterProps) {
  const { siteName, contact } = getSiteConfig();
  const year = getCopyrightYear();
  const copyright = formatContentTemplate(content.copyrightTemplate, {
    year: String(year),
  });

  return (
    <footer
      id="contact"
      className="border-t border-brand-100 bg-brand-50 text-ink-700"
      data-section-id="footer"
    >
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-12 lg:px-8">
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 md:gap-10 lg:grid-cols-[max-content_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <div className="col-span-2 flex items-center gap-4 md:col-span-1 md:block">
            <img
              src="/images/brand/siutindei-logo-stacked.svg"
              alt={siteName}
              width={175}
              height={150}
              className="h-auto w-20 shrink-0 md:w-40"
            />
            <p className="text-sm md:mt-2">{content.tagline}</p>
          </div>
          <div className="col-span-2 min-w-0 text-sm md:col-span-1">
            <p className="font-semibold text-ink-900">
              {content.contactHeading}
            </p>
            <div className="mt-1 flex flex-wrap gap-x-6 md:mt-2 md:block md:space-y-1">
              {contact.email ? (
                <p>
                  <a
                    href={`mailto:${contact.email}`}
                    className={`${FOOTER_LINK_CLASS} underline-offset-2 hover:underline`}
                  >
                    {contact.email}
                  </a>
                </p>
              ) : null}
              {contact.whatsappUrl ? (
                <p>
                  <TrackedWhatsappLink
                    href={contact.whatsappUrl}
                    leadType="whatsapp_footer"
                    target="_blank"
                    rel="noreferrer noopener"
                    className={`${FOOTER_LINK_CLASS} underline-offset-2 hover:underline`}
                  >
                    {contact.whatsappDisplay
                      ? `WhatsApp ${contact.whatsappDisplay}`
                      : 'WhatsApp'}
                  </TrackedWhatsappLink>
                </p>
              ) : null}
              {contact.instagramUrl ? (
                <p>
                  <a
                    href={contact.instagramUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className={`${FOOTER_LINK_CLASS} underline-offset-2 hover:underline`}
                  >
                    Instagram
                  </a>
                </p>
              ) : null}
            </div>
          </div>
          {content.columns.map((column) => (
            <div key={column.title} className="min-w-0">
              <p className="text-sm font-semibold text-ink-900">
                {column.title}
              </p>
              <ul className="mt-1 text-sm md:mt-3 md:space-y-2">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={localizeHref(link.href, locale)}
                      className={`${FOOTER_LINK_CLASS} hover:text-brand-600 hover:underline`}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-5 border-t border-brand-200 pt-4 text-xs md:mt-10 md:pt-6">
          {copyright}
        </p>
      </div>
    </footer>
  );
}
