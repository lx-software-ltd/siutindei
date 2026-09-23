import Link from 'next/link';

import type { FooterContent, Locale } from '@/content';
import { formatContentTemplate } from '@/content/content-field-utils';
import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { localizeHref } from '@/lib/locale-routing';
import { getCopyrightYear, getSiteConfig } from '@/lib/site-config';

interface FooterProps {
  readonly locale: Locale;
  readonly content: FooterContent;
}

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
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <img
              src="/images/brand/siutindei-logo-stacked.svg"
              alt={siteName}
              width={175}
              height={150}
              className="h-auto w-40"
            />
            <p className="mt-2 text-sm">{content.tagline}</p>
            <div className="mt-4 text-sm">
              <p className="font-semibold text-ink-900">
                {content.contactHeading}
              </p>
              {contact.email ? (
                <p className="mt-2">
                  <a
                    href={`mailto:${contact.email}`}
                    className="underline-offset-2 hover:underline"
                  >
                    {contact.email}
                  </a>
                </p>
              ) : null}
              {contact.whatsappUrl ? (
                <p className="mt-1">
                  <TrackedWhatsappLink
                    href={contact.whatsappUrl}
                    leadType="whatsapp_footer"
                    target="_blank"
                    rel="noreferrer noopener"
                    className="underline-offset-2 hover:underline"
                  >
                    {contact.whatsappDisplay
                      ? `WhatsApp ${contact.whatsappDisplay}`
                      : 'WhatsApp'}
                  </TrackedWhatsappLink>
                </p>
              ) : null}
              {contact.instagramUrl ? (
                <p className="mt-1">
                  <a
                    href={contact.instagramUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="underline-offset-2 hover:underline"
                  >
                    Instagram
                  </a>
                </p>
              ) : null}
            </div>
          </div>
          {content.columns.map((column) => (
            <div key={column.title}>
              <p className="text-sm font-semibold text-ink-900">
                {column.title}
              </p>
              <ul className="mt-3 space-y-2 text-sm">
                {column.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={localizeHref(link.href, locale)}
                      className="hover:text-brand-600 hover:underline"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="mt-10 border-t border-brand-200 pt-6 text-xs">
          {copyright}
        </p>
      </div>
    </footer>
  );
}
