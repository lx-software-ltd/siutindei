import enContent from '@/content/en.json';
import zhHKContent from '@/content/zh-HK.json';
import { formatContentTemplate } from '@/content/content-field-utils';
import { categoryLandingPath, staticActivityPath } from '@/lib/activities/activity-href';
import { catalogueCategories, catalogueListings } from '@/lib/activities/catalogue-snapshot';
import { catalogueScopePlace } from '@/lib/activities/landing-page-data';
import { listingOrgName, listingTitle } from '@/lib/activities/listing-utils';
import { labelForLocale } from '@/lib/home-wizard/choices';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

export const LLMS_TXT_ACTIVITY_LIMIT = 200;

function link(siteOrigin: string, label: string, path: string, note?: string): string {
  const url = new URL(path, siteOrigin).toString();
  return note ? `- [${label}](${url}): ${note}` : `- [${label}](${url})`;
}

/**
 * `/llms.txt` (llmstxt.org): a Markdown index of the pages that answer
 * what the site is and which activities it lists.
 */
export function buildLlmsTxt(siteOrigin: string, siteName: string): string {
  const en = enContent;
  const zh = zhHKContent;
  const listings = catalogueListings();
  const categories = catalogueCategories();
  const place = catalogueScopePlace('en', en.discovery);
  const zhPlace = catalogueScopePlace('zh-HK', zh.discovery);
  const count = (value: number) =>
    formatContentTemplate(en.activitiesPage.activityCountTemplate, { count: value });

  const lines = [
    `# ${siteName} (小天地)`,
    '',
    `> ${en.seo.home.description}`,
    '',
    ...en.pages.about.summary.paragraphs.flatMap((paragraph) => [
      formatContentTemplate(paragraph, { placeFull: place.placeFull }),
      '',
    ]),
    '## About',
    '',
    link(siteOrigin, en.pages.about.title, localizePath(ROUTES.about, 'en'), en.pages.about.summary.heading),
    link(siteOrigin, zh.pages.about.title, localizePath(ROUTES.about, 'zh-HK'), '中文'),
    link(siteOrigin, en.seo.privacy.title, localizePath(ROUTES.privacy, 'en')),
    link(siteOrigin, en.seo.terms.title, localizePath(ROUTES.terms, 'en')),
  ];

  if (listings.length > 0) {
    lines.push(
      '',
      '## Activities',
      '',
      link(
        siteOrigin,
        formatContentTemplate(en.activitiesPage.hubHeadingTemplate, { ...place }),
        localizePath(ROUTES.activities, 'en'),
        count(listings.length),
      ),
      link(
        siteOrigin,
        formatContentTemplate(zh.activitiesPage.hubHeadingTemplate, { ...zhPlace }),
        localizePath(ROUTES.activities, 'zh-HK'),
        '中文',
      ),
      ...categories.map((category) =>
        link(
          siteOrigin,
          formatContentTemplate(en.activitiesPage.categoryHeadingTemplate, {
            ...place,
            category: labelForLocale(category.labels, 'en'),
          }),
          categoryLandingPath('en', category.typeId),
          count(category.listings.length),
        ),
      ),
      '',
      '## Optional',
      '',
      ...listings
        .slice(0, LLMS_TXT_ACTIVITY_LIMIT)
        .map((listing) =>
          link(
            siteOrigin,
            listingTitle('en', listing),
            staticActivityPath('en', listing.activity.id),
            listingOrgName('en', listing),
          ),
        ),
    );
  }

  return `${lines.join('\n')}\n`;
}
