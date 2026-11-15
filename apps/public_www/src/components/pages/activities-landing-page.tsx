import Link from 'next/link';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { ActivityBreadcrumb } from '@/components/sections/activity-detail/activity-breadcrumb';
import { ListingGrid } from '@/components/sections/listings/listing-grid';
import { CategoryLinkNav } from '@/components/shared/category-link-nav';
import { StaticActivityPages } from '@/components/shared/static-activity-pages';
import { formatContentTemplate } from '@/content/content-field-utils';
import type { ActivityBreadcrumbItem } from '@/lib/activities/activity-page-data';
import type { CategoryLinkGroup, LandingFacts } from '@/lib/activities/landing-page-data';
import type { ActivityListing } from '@/lib/activities/types';

/** A group of cards: one per kind on the hub, a single one on a landing page. */
export interface LandingSection {
  readonly id: string;
  readonly heading: string;
  readonly listings: readonly ActivityListing[];
  /** The kind's own page, when the hub section has one. */
  readonly moreHref?: string | null;
  readonly moreLabel?: string | null;
}

interface ActivitiesLandingPageProps {
  readonly locale: Locale;
  readonly content: SiteContent;
  readonly heading: string;
  readonly intro: string;
  readonly breadcrumbs: readonly ActivityBreadcrumbItem[];
  readonly facts: LandingFacts;
  readonly coverage: string | null;
  /** The kinds, then the topics, each under its own heading. */
  readonly categoryGroups: readonly CategoryLinkGroup[];
  readonly sections: readonly LandingSection[];
  readonly searchHref: string;
}

export function ActivitiesLandingPage({
  locale,
  content,
  heading,
  intro,
  breadcrumbs,
  facts,
  coverage,
  categoryGroups,
  sections,
  searchHref,
}: ActivitiesLandingPageProps) {
  const hasListings = sections.some((section) => section.listings.length > 0);
  const copy = content.activitiesPage;
  const discovery = content.discovery;
  const factRows = [
    { id: 'ages', label: copy.agesLabel, value: facts.ages },
    { id: 'days', label: copy.daysLabel, value: facts.days },
    { id: 'prices', label: copy.pricesLabel, value: facts.prices },
  ].filter((row): row is { id: string; label: string; value: string } => Boolean(row.value));
  const questions = [
    facts.ages
      ? { question: copy.agesQuestion, answer: formatContentTemplate(copy.agesAnswerTemplate, { ages: facts.ages }) }
      : null,
    facts.days
      ? { question: copy.daysQuestion, answer: formatContentTemplate(copy.daysAnswerTemplate, { days: facts.days }) }
      : null,
    facts.prices
      ? {
          question: copy.pricesQuestion,
          answer: formatContentTemplate(copy.pricesAnswerTemplate, { prices: facts.prices }),
        }
      : null,
    hasListings ? { question: copy.joinQuestion, answer: copy.joinAnswer } : null,
  ].filter((item): item is { question: string; answer: string } => item !== null);

  return (
    <article className="mx-auto max-w-6xl px-4 pb-14 pt-2 sm:px-6 lg:px-8">
      <ActivityBreadcrumb backHref={null} items={breadcrumbs} copy={content.activityDetail} />
      <header className="mt-2 max-w-3xl">
        <h1 className="text-3xl font-bold text-ink-900 sm:text-4xl">{heading}</h1>
        <p className="mt-3 text-base text-ink-700">{intro}</p>
        {coverage ? (
          <p data-coverage className="mt-2 text-sm text-ink-500">
            {coverage}
          </p>
        ) : null}
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

      {categoryGroups.map((group) => (
        <CategoryLinkNav
          key={group.id}
          group={group}
          countTemplate={copy.activityCountTemplate}
          headingLevel="h2"
          className="mt-8"
        />
      ))}

      {sections.map((section) => (
        <section
          key={section.id}
          aria-labelledby={`activities-list-${section.id}`}
          className="mt-8"
        >
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2
              id={`activities-list-${section.id}`}
              className="text-lg font-semibold text-ink-900"
            >
              {section.heading}
            </h2>
            {section.moreHref && section.moreLabel ? (
              <Link
                href={section.moreHref}
                className="text-sm font-semibold text-ink-900 underline underline-offset-4"
              >
                {section.moreLabel}
              </Link>
            ) : null}
          </div>
          <StaticActivityPages ids={section.listings.map((listing) => listing.activity.id)}>
            <ListingGrid
              locale={locale}
              listings={section.listings}
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
      ))}

      {questions.length > 0 ? (
        <section aria-labelledby="activities-questions" className="mt-10 max-w-3xl">
          <h2 id="activities-questions" className="text-lg font-semibold text-ink-900">
            {copy.questionsHeading}
          </h2>
          {questions.map((item) => (
            <div key={item.question} className="mt-4">
              <h3 className="font-semibold text-ink-900">{item.question}</h3>
              <p className="mt-1 text-ink-700">{item.answer}</p>
            </div>
          ))}
        </section>
      ) : null}

      <p className="mt-8">
        <Link href={searchHref} className="font-semibold text-ink-900 underline underline-offset-4">
          {copy.searchLinkLabel}
        </Link>
      </p>
    </article>
  );
}
