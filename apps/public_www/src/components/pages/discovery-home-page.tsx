import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { DiscoveryHomeSection } from '@/components/sections/discovery/discovery-home-section';
import { SmallWorldHero } from '@/components/sections/hero/small-world-hero';
import { FeaturesSection } from '@/components/sections/grid/features-section';
import {
  BUBBLE_BUILD_SEED,
  pickBubbleIdsForSeed,
} from '@/lib/small-world/kawaii-bubbles';

interface DiscoveryHomePageProps {
  readonly locale: Locale;
  readonly content: SiteContent;
}

export function DiscoveryHomePage({ locale, content }: DiscoveryHomePageProps) {
  const bubbleIds = pickBubbleIdsForSeed(BUBBLE_BUILD_SEED);
  return (
    <>
      <p className="sr-only">{content.discovery.pageTitle}</p>
      <SmallWorldHero
        locale={locale}
        copy={content.smallWorld}
        searchBarLabels={content.navbar.searchBar}
        bubbleIds={bubbleIds}
      />
      <DiscoveryHomeSection locale={locale} copy={content.discovery} />
      <section className="border-t border-brand-100 bg-brand-50 py-10">
        <div className="mx-auto max-w-5xl px-4 text-center sm:px-6">
          <h2 className="text-2xl font-bold text-ink-900">
            {content.hostCta.title}
          </h2>
          <p className="mt-3 text-ink-700">{content.hostCta.description}</p>
          <a
            href={content.hostCta.href}
            className="link-unadorned mt-6 inline-flex min-h-11 items-center rounded-full bg-brand-500 px-6 py-3 text-sm font-semibold text-ink-900 hover:bg-brand-600"
          >
            {content.hostCta.buttonLabel}
          </a>
        </div>
      </section>
      <FeaturesSection content={content.features} />
    </>
  );
}
