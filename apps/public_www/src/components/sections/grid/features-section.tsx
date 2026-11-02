import type { FeaturesContent } from '@/content/types';
interface FeaturesSectionProps {
  readonly content: FeaturesContent;
}

export function FeaturesSection({ content }: FeaturesSectionProps) {
  return (
    <section
      id="features"
      className="bg-white"
      data-section-id="features"
    >
      <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6 sm:py-24">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl">
            {content.title}
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-ink-700">
            {content.description}
          </p>
        </div>
        <ul className="mt-12 grid gap-8 sm:grid-cols-3">
          {content.items.map((feature) => (
            <li
              key={feature.title}
              className="rounded-xl border border-brand-100 bg-brand-50 p-6"
            >
              <h3 className="text-lg font-semibold text-brand-700">
                {feature.title}
              </h3>
              <p className="mt-2 text-sm leading-6 text-ink-700">
                {feature.description}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
