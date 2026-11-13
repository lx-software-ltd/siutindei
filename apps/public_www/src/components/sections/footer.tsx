import Link from 'next/link';

import type { Locale } from '@/content/locales';
import type { FooterContent } from '@/content/types';
import { formatContentTemplate } from '@/content/content-field-utils';
import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { localizeHref } from '@/lib/locale-routing';
import {
  getCopyrightYear,
  getSiteConfig,
  LX_SOFTWARE_NAME,
  LX_SOFTWARE_URL,
} from '@/lib/site-config';

interface FooterProps {
  readonly locale: Locale;
  readonly content: FooterContent;
}

/** Phones stack the links tightly, so each one pads out its own tap area. */
const FOOTER_LINK_CLASS = 'inline-block py-1.5 md:inline md:py-0';

/** Icon buttons keep a 44px target on every width. */
const CONTACT_ICON_CLASS =
  'link-unadorned inline-flex h-11 w-11 items-center justify-center transition-transform hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0';

function contactIconName(label: string, detail: string): string {
  return detail ? `${label} ${detail}` : label;
}

function CopyrightNotice({ text }: { readonly text: string }) {
  const brandAt = text.indexOf(LX_SOFTWARE_NAME);
  if (brandAt < 0) {
    return text;
  }

  return (
    <>
      {text.slice(0, brandAt)}
      <a href={LX_SOFTWARE_URL} target="_blank" rel="noreferrer noopener">
        {LX_SOFTWARE_NAME}
      </a>
      {text.slice(brandAt + LX_SOFTWARE_NAME.length)}
    </>
  );
}

function ContactIcon({
  src,
  label,
}: {
  readonly src: string;
  readonly label: string;
}) {
  return (
    <img
      src={src}
      alt={label}
      width={36}
      height={36}
      decoding="async"
      className="h-9 w-9 shrink-0"
    />
  );
}

export function Footer({ locale, content }: FooterProps) {
  const { siteName, contact } = getSiteConfig();
  const year = getCopyrightYear();
  const copyright = formatContentTemplate(content.copyrightTemplate, {
    year: String(year),
  });
  const iconLabels = content.contactIconLabels;

  return (
    <footer
      id="contact"
      className="border-t border-brand-100 bg-brand-50 text-ink-700"
      data-section-id="footer"
    >
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-12 lg:px-8">
        {/* Phones put the icons on the logo's row, flush right. Wider screens center them. */}
        <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-5 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:gap-x-10">
          <img
            src="/images/brand/siutindei-logo-stacked.svg"
            alt={siteName}
            width={175}
            height={150}
            className="col-start-1 row-start-1 h-auto w-20 shrink-0 justify-self-start md:w-40"
          />
          <div className="col-start-2 row-start-1 flex flex-wrap justify-end gap-1 md:justify-center">
            {contact.email ? (
              <a
                href={`mailto:${contact.email}`}
                className={CONTACT_ICON_CLASS}
              >
                <ContactIcon
                  src="/images/contact/email.svg"
                  label={contactIconName(iconLabels.email, contact.email)}
                />
              </a>
            ) : null}
            {contact.whatsappUrl ? (
              <TrackedWhatsappLink
                href={contact.whatsappUrl}
                leadType="whatsapp_footer"
                target="_blank"
                rel="noreferrer noopener"
                className={CONTACT_ICON_CLASS}
              >
                <ContactIcon
                  src="/images/contact/whatsapp.svg"
                  label={contactIconName(
                    iconLabels.whatsapp,
                    contact.whatsappDisplay,
                  )}
                />
              </TrackedWhatsappLink>
            ) : null}
            {contact.instagramUrl ? (
              <a
                href={contact.instagramUrl}
                target="_blank"
                rel="noreferrer noopener"
                className={CONTACT_ICON_CLASS}
              >
                <ContactIcon
                  src="/images/contact/instagram.svg"
                  label={iconLabels.instagram}
                />
              </a>
            ) : null}
            {contact.facebookUrl ? (
              <a
                href={contact.facebookUrl}
                target="_blank"
                rel="noreferrer noopener"
                className={CONTACT_ICON_CLASS}
              >
                <ContactIcon
                  src="/images/contact/facebook.svg"
                  label={iconLabels.facebook}
                />
              </a>
            ) : null}
          </div>
          <div className="col-span-2 row-start-2 grid grid-cols-2 gap-x-6 md:col-span-1 md:col-start-3 md:row-start-1 md:w-max md:justify-self-end md:gap-x-10">
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
        </div>
        <p className="mt-5 border-t border-brand-200 pt-4 text-center text-xs md:mt-10 md:pt-6">
          <CopyrightNotice text={copyright} />
        </p>
      </div>
    </footer>
  );
}
