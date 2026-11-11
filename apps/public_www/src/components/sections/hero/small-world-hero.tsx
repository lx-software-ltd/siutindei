import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { HeroScopeSigns } from '@/components/sections/hero/hero-scope-signs';
import { HeroSearchBar } from '@/components/sections/hero/hero-search-bar';
import { FloatingKawaiiBubbles } from '@/components/sections/hero/floating-kawaii-bubbles';
import { SearchNavigator } from '@/components/sections/hero/search-navigator';
import type { HeroScopeSign } from '@/lib/home-wizard/area-scope';
import type { BubbleId } from '@/lib/small-world/kawaii-bubbles';

interface SmallWorldHeroProps {
  readonly locale: Locale;
  readonly copy: SiteContent['smallWorld'];
  readonly searchBarLabels: SiteContent['navbar']['searchBar'];
  readonly bubbleIds: readonly BubbleId[];
  readonly scopeSigns?: readonly HeroScopeSign[];
}

const NO_SCOPE_SIGNS: readonly HeroScopeSign[] = [];

/**
 * The immersive "Small World" hero: random kawaii Hong Kong pictures
 * in flat circular bubbles, with discovery search front and center.
 */
export function SmallWorldHero({
  locale,
  copy,
  searchBarLabels,
  bubbleIds,
  scopeSigns = NO_SCOPE_SIGNS,
}: SmallWorldHeroProps) {
  return (
    <section className="small-world-hero" aria-label={copy.sceneAriaLabel}>
      <div className="small-world-hero__stars" aria-hidden="true" />
      <FloatingKawaiiBubbles
        copy={copy}
        ids={bubbleIds}
        hideCorner={scopeSigns.length > 0}
      />
      {scopeSigns.length > 0 ? <HeroScopeSigns signs={scopeSigns} /> : null}
      <div className="relative z-10 mx-auto max-w-3xl px-4 pb-16 pt-8 text-center sm:px-6 md:pb-24 md:pt-12">
        <img
          src="/images/brand/siutindei-logo-stacked.svg"
          alt=""
          width={175}
          height={150}
          aria-hidden="true"
          className="mx-auto h-auto w-40 md:w-48"
        />
        <h1 className="brand-title mt-4 text-balance text-3xl font-bold leading-tight text-ink-900 sm:text-4xl md:text-[52px]">
          {copy.title}
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-balance text-base text-ink-700 md:text-lg">
          {copy.subtitle}
        </p>
        <div className="mt-8">
          <HeroSearchBar locale={locale} labels={searchBarLabels} />
        </div>
        <SearchNavigator locale={locale} copy={copy.navigator} />
      </div>
    </section>
  );
}
