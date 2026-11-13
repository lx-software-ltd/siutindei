import Link from 'next/link';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityBreadcrumb } from '@/components/sections/activity-detail/activity-breadcrumb';
import { ListingGrid } from '@/components/sections/listings/listing-grid';
import { StaticActivityPages } from '@/components/shared/static-activity-pages';
import { formatContentTemplate } from '@/content/content-field-utils';
import type { ActivityBreadcrumbItem } from '@/lib/activities/activity-page-data';
import type { LandingFacts } from '@/lib/activities/landing-page-data';
import type { ActivityListing } from '@/lib/activities/types';

export interface LandingCategoryLink {
  readonly typeId: string;
  readonly label: string;
  readonly href: string;
  readonly count: number;
}

interface ActivitiesLandingPageProps {
  readonly locale: Locale;
  readonly content: SiteContent;
  readonly heading: string;
  readonly intro: string;
  readonly breadcrumbs: readonly ActivityBreadcrumbItem[];
  readonly facts: LandingFacts;
  readonly categoriesHeading: string;
  readonly categories: readonly LandingCategoryLink[];
  readonly listings: readonly ActivityListing[];
  readonly searchHref: string;
}

export function ActivitiesLandingPage({
  locale,
  content,
  heading,
  intro,
  breadcrumbs,
  facts,
  categoriesHeading,
  categories,
  listings,
  searchHref,
}: ActivitiesLandingPageProps) {
  const copy = content.activitiesPage;
  const discovery = content.discovery;
  const factRows = [
    { id: 'ages', label: copy.agesLabel, value: facts.ages },
    { id: 'days', label: copy.daysLabel, value: facts.days },
    { id: 'prices', label: copy.pricesLabel, value: facts.prices },
  ].filter((row): row is { id: string; label: string; value: string } => Boolean(row.value));

  return (
    <article className="mx-auto max-w-6xl px-4 pb-14 pt-2 sm:px-6 lg:px-8">
      <ActivityBreadcrumb backHref={null} items={breadcrumbs} copy={content.activityDetail} />
      <header className="mt-2 max-w-3xl">
        <h1 className="text-3xl font-bold text-ink-900 sm:text-4xl">{heading}</h1>
        <p className="mt-3 text-base text-ink-700">{intro}</p>
      </header>

      {factRows.length > 0 ? (
        <section aria-labelledby="activities-at-a-glance" className="mt-6 max-w-3xl">
          <h2 id="activities-at-a-glance" className="text-lg font-semibold text-ink-900">
            {copy.atAGlanceHeading}
          </h2>
          <dl className="mt-2 grid gap-3 sm:grid-cols-3">
            {factRows.map((row) => (
              <div key={row.id} className="rounded-xl border border-brand-100 bg-brand-50 px-4 py-3">
                <dt className="text-sm text-ink-700">{row.label}</dt>
                <dd className="mt-1 font-semibold text-ink-900">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {categories.length > 0 ? (
        <nav aria-labelledby="activities-by-type" className="mt-8">
          <h2 id="activities-by-type" className="text-lg font-semibold text-ink-900">
            {categoriesHeading}
          </h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {categories.map((category) => (
              <li key={category.typeId}>
                <Link
                  href={category.href}
                  className="link-unadorned inline-flex min-h-11 items-center gap-2 rounded-full border border-brand-200 bg-white px-4 text-sm font-semibold text-ink-900 hover:bg-brand-50"
                >
                  {category.label}
                  <span className="font-normal text-ink-700">
                    {formatContentTemplate(copy.activityCountTemplate, { count: category.count })}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}

      <section aria-labelledby="activities-list" className="mt-8">
        <h2 id="activities-list" className="mb-4 text-lg font-semibold text-ink-900">
          {copy.allActivitiesHeading}
        </h2>
        <StaticActivityPages ids={listings.map((listing) => listing.activity.id)}>
          <ListingGrid
            locale={locale}
            listings={listings}
            isLoading={false}
            labels={{
              parentVerified: discovery.parentVerifiedLabel,
              freeTrial: discovery.freeTrialLabel,
              imageFallback: discovery.imageFallbackLabel,
              locationsCount: discovery.locationsCountLabel,
              detailsOnRequest: discovery.detailsOnRequestLabel,
              empty: copy.emptyLabel,
            }}
          />
        </StaticActivityPages>
      </section>

      <p className="mt-8">
        <Link href={searchHref} className="font-semibold text-ink-900 underline underline-offset-4">
          {copy.searchLinkLabel}
        </Link>
      </p>
    </article>
  );
}
