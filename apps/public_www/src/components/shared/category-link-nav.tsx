import Link from 'next/link';

import { formatContentTemplate } from '@/content/content-field-utils';
import type { CategoryLinkGroup } from '@/lib/activities/landing-page-data';

interface CategoryLinkNavProps {
  readonly group: CategoryLinkGroup;
  readonly countTemplate: string;
  readonly headingLevel: 'h2' | 'h3';
  readonly className?: string;
}

export function CategoryLinkNav({
  group,
  countTemplate,
  headingLevel: Heading,
  className,
}: CategoryLinkNavProps) {
  if (group.links.length === 0) {
    return null;
  }
  const headingId = `category-links-${group.id}`;
  return (
    <nav aria-labelledby={headingId} className={className}>
      <Heading id={headingId} className="text-lg font-semibold text-ink-900">
        {group.heading}
      </Heading>
      <ul className="mt-3 flex flex-wrap gap-2">
        {group.links.map((link) => (
          <li key={link.typeId}>
            <Link
              href={link.href}
              className="link-unadorned inline-flex min-h-11 items-center gap-2 rounded-full border border-brand-200 bg-white px-4 text-sm font-semibold text-ink-900 hover:bg-brand-50"
            >
              {link.label}
              <span className="font-normal text-ink-700">
                {formatContentTemplate(countTemplate, { count: link.count })}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
