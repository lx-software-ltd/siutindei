import type { Locale } from '@/content/locales';
import type { HeroContent } from '@/content/types';
import { localizeHref } from '@/lib/locale-routing';

interface HeroSectionProps {
  readonly locale: Locale;
  readonly content: HeroContent;
  readonly eyebrow: string;
  readonly primaryCtaLabel: string;
  readonly primaryCtaHref: string;
  readonly secondaryCtaLabel: string;
  readonly secondaryCtaHref: string;
}

export function HeroSection({
  locale,
  content,
  eyebrow,
  primaryCtaLabel,
  primaryCtaHref,
  secondaryCtaLabel,
  secondaryCtaHref,
}: HeroSectionProps) {
  return (
    <section
      id="hero"
      className="border-b border-brand-100 bg-white"
      data-section-id="hero"
    >
      <div className="mx-auto max-w-5xl px-4 py-12 text-center sm:px-6 sm:py-16">
        <p className="text-sm font-semibold uppercase tracking-widest text-ink-500">
          {eyebrow}
        </p>
        <h1 className="mt-4 text-3xl font-bold tracking-tight text-ink-900 sm:text-5xl">
          {content.title}
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-ink-700">
          {content.subtitle}
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <a
            href={localizeHref(primaryCtaHref, locale)}
            className={
              'link-unadorned inline-flex min-h-11 items-center ' +
              'justify-center rounded-lg border border-ink-900/20 ' +
              'bg-accent-500 px-6 py-3 text-sm font-semibold ' +
              'text-ink-900 transition hover:bg-accent-600'
            }
          >
            {primaryCtaLabel}
          </a>
          <a
            href={localizeHref(secondaryCtaHref, locale)}
            className={
              'link-unadorned inline-flex min-h-11 items-center ' +
              'justify-center rounded-lg border border-ink-900/15 ' +
              'bg-white px-6 py-3 text-sm font-semibold text-ink-900 ' +
              'transition hover:bg-brand-50'
            }
          >
            {secondaryCtaLabel}
          </a>
        </div>
      </div>
    </section>
  );
}
