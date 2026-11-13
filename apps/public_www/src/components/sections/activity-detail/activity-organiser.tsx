import type { Locale } from '@/content/locales';
import { contactLinks, type ContactLinkKind } from '@/lib/activities/contact-links';
import { descriptionParagraphs } from '@/lib/activities/detail-view';
import type { OrganizationContact } from '@/lib/activities/types';
import { formatTemplate } from '@/lib/format-template';

import { DetailIcon, type DetailIconName } from './detail-icon';
import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

const ICON_FOR_KIND: Record<ContactLinkKind, DetailIconName> = {
  website: 'globe',
  phone: 'phone',
  email: 'mail',
  whatsapp: 'chat',
  instagram: 'link',
  facebook: 'link',
  tiktok: 'link',
  twitter: 'link',
  xiaohongshu: 'link',
  wechat: 'chat',
};

interface ActivityOrganiserProps {
  readonly locale: Locale;
  readonly name: string;
  readonly description: string;
  readonly logoUrl: string | null;
  readonly contact: OrganizationContact | null;
  readonly updatedAt: string | null;
  readonly copy: ActivityDetailCopy;
}

function formatUpdated(locale: Locale, value: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(locale === 'zh-HK' ? 'zh-HK' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Hong_Kong',
  }).format(date);
}

export function ActivityOrganiser({
  locale,
  name,
  description,
  logoUrl,
  contact,
  updatedAt,
  copy,
}: ActivityOrganiserProps) {
  const links = contactLinks(contact);
  const paragraphs = descriptionParagraphs(description);
  const updated = formatUpdated(locale, updatedAt);
  const kindLabels = copy.contactKindLabels as Record<ContactLinkKind, string>;
  return (
    <DetailSection id="organiser" title={copy.organiserHeading}>
      <div className="flex items-center gap-3">
        {logoUrl ? (
          <img
            src={logoUrl}
            alt=""
            width={56}
            height={56}
            aria-hidden="true"
            className="h-14 w-14 rounded-xl border border-brand-100 bg-white object-contain p-1"
          />
        ) : null}
        <p className="text-lg font-semibold text-ink-900">{name}</p>
      </div>
      {paragraphs.length > 0 ? (
        <div className="mt-3 max-w-prose space-y-3 whitespace-pre-line text-sm leading-6 text-ink-700">
          {paragraphs.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
      ) : null}
      {links.length > 0 ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-ink-900">{copy.contactHeading}</h3>
          <ul className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {links.map((link) => {
              const label = kindLabels[link.kind];
              const body = (
                <>
                  <DetailIcon name={ICON_FOR_KIND[link.kind]} className="h-[18px] w-[18px] shrink-0" />
                  <span className="min-w-0">
                    <span className="block text-xs text-ink-500">{label}</span>
                    <span className="block truncate text-sm font-medium text-ink-900">
                      {link.href ? (
                        <span className="underline underline-offset-2">{link.text}</span>
                      ) : (
                        link.text
                      )}
                    </span>
                  </span>
                </>
              );
              const className =
                'flex min-h-11 w-full min-w-0 items-center gap-3 overflow-hidden rounded-lg border border-brand-100 px-3 py-2';
              return (
                <li key={`${link.kind}-${link.text}`} className="min-w-0">
                  {link.href ? (
                    <a
                      href={link.href}
                      {...(link.href.startsWith('http')
                        ? { target: '_blank', rel: 'noreferrer noopener nofollow' }
                        : {})}
                      className={`link-unadorned ${className} hover:bg-brand-50`}
                    >
                      {body}
                    </a>
                  ) : (
                    <p className={className}>{body}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {updated ? (
        <p className="mt-4 text-xs text-ink-500">
          {formatTemplate(copy.updatedLabel, { date: updated })}
        </p>
      ) : null}
    </DetailSection>
  );
}
