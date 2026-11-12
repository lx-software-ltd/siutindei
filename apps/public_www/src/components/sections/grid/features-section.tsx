import type { SiteContent } from '@/content/types';

const CONTACT_SECTION_ID = 'write-to-me';

interface FeaturesSectionProps {
  readonly content: SiteContent;
}

export function FeaturesSection({ content }: FeaturesSectionProps) {
  const about = content.pages.about;
  const cards = about.sections.filter(
    (section) => section.id !== CONTACT_SECTION_ID,
  );

  return (
    <section
      id="features"
      className="bg-white"
      data-section-id="features"
    >
      <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6 sm:py-24">
        <div className="text-center">
          <h2 className="text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl">
            {content.features.title}
          </h2>
          {about.intro.map((paragraph) => (
            <p
              key={paragraph}
              className="mx-auto mt-4 max-w-2xl text-lg text-ink-700"
            >
              {paragraph}
            </p>
          ))}
        </div>
        <ul className="mt-12 grid gap-8 sm:grid-cols-2">
          {cards.map((section) => (
            <li
              key={section.id}
              className="rounded-xl border border-brand-100 bg-brand-50 p-6 text-left"
            >
              <h3 className="text-lg font-semibold text-brand-700">
                {section.heading}
              </h3>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph} className="mt-2 text-sm leading-6 text-ink-700">
                  {paragraph}
                </p>
              ))}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
