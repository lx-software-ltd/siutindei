import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import ActivitiesHubPage from '@/app/[locale]/activities/page';
import { ActivitiesLandingPage } from '@/components/pages/activities-landing-page';
import { PageLayout } from '@/components/shared/page-layout';
import { getContent } from '@/content';
import { clearCatalogueCacheForTests } from '@/lib/activities/catalogue-snapshot';
import { SNAPSHOT_FIXTURE } from '../helpers/catalogue-fixture';
import { withChromeCopy } from '../helpers/chrome-copy';

vi.mock('next/navigation', () => ({
  usePathname: () => '/en/activities/',
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe('ActivitiesLandingPage questions', () => {
  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_SITE_ORIGIN', 'https://example.com');
    vi.stubEnv('NEXT_PUBLIC_SEARCH_AREA_SCOPE', '');
    vi.stubEnv('NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED', 'false');
    vi.stubEnv('PUBLIC_WWW_CATALOGUE_SNAPSHOT_PATH', SNAPSHOT_FIXTURE);
    clearCatalogueCacheForTests();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    clearCatalogueCacheForTests();
  });

  it('answers ages, days, prices, and how to join from the catalogue', async () => {
    const content = getContent('en');
    const copy = content.activitiesPage;
    render(
      withChromeCopy(
        <PageLayout locale="en" navbarContent={content.navbar} footerContent={content.footer}>
          {await ActivitiesHubPage({ params: Promise.resolve({ locale: 'en' }) })}
        </PageLayout>,
      ),
    );

    const questions = screen.getByRole('region', { name: copy.questionsHeading });
    const headings = within(questions)
      .getAllByRole('heading', { level: 3 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      copy.agesQuestion,
      copy.daysQuestion,
      copy.pricesQuestion,
      copy.joinQuestion,
    ]);
    expect(questions.textContent).not.toMatch(/\{[a-z]+\}/);
    expect(questions.textContent).toContain(copy.joinAnswer);
  });

  it('groups the hub by kind, links the kind page, and skips coverage without dates', async () => {
    const content = getContent('en');
    const copy = content.activitiesPage;
    const { container } = render(
      withChromeCopy(
        <PageLayout locale="en" navbarContent={content.navbar} footerContent={content.footer}>
          {await ActivitiesHubPage({ params: Promise.resolve({ locale: 'en' }) })}
        </PageLayout>,
      ),
    );

    const classes = screen.getByRole('heading', { level: 2, name: copy.kindPages.classes });
    const section = classes.closest('section') as HTMLElement;
    expect(within(section).getByRole('link', { name: /^See all \d+/ })).toHaveAttribute(
      'href',
      '/en/activities/classes',
    );
    expect(screen.queryByRole('heading', { level: 2, name: copy.kindPages.places })).toBeNull();
    expect(container.querySelector('[data-coverage]')).toBeNull();
  });

  it('leaves out questions the data cannot answer', () => {
    const content = getContent('en');
    render(
      <ActivitiesLandingPage
        locale="en"
        content={content}
        heading="Activities"
        intro="Intro"
        breadcrumbs={[]}
        facts={{ ages: '3 to 8 years', days: null, prices: null }}
        categoriesHeading="Types"
        coverage={null}
        categories={[]}
        sections={[]}
        searchHref="/en/search/"
      />,
    );

    const questions = screen.getByRole('region', { name: content.activitiesPage.questionsHeading });
    expect(within(questions).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      content.activitiesPage.agesQuestion,
    ]);
    expect(questions).toHaveTextContent('3 to 8 years.');
  });
});
