import type { LegalContent } from '@/content/types';
type LegalDocument = LegalContent['privacy'];
type LegalSection = LegalDocument['sections'][number];

interface LegalPageProps {
  readonly document: LegalDocument;
  readonly lastUpdatedLabel: LegalContent['lastUpdatedLabel'];
  readonly lastUpdated: LegalContent['lastUpdated'];
  readonly onThisPageLabel: LegalContent['onThisPageLabel'];
}

function LegalSectionBlock({ section }: { readonly section: LegalSection }) {
  return (
    <section id={section.id} className="scroll-mt-24">
      <h2 className="text-xl font-semibold text-ink-900">{section.heading}</h2>
      {section.paragraphs.map((paragraph) => (
        <p key={paragraph} className="mt-3 leading-7 text-ink-700">
          {paragraph}
        </p>
      ))}
      {section.bullets.length > 0 ? (
        <ul className="mt-3 list-disc space-y-2 pl-6 leading-7 text-ink-700">
          {section.bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function LegalPage({
  document,
  lastUpdatedLabel,
  lastUpdated,
  onThisPageLabel,
}: LegalPageProps) {
  return (
    <article
      className="mx-auto max-w-3xl px-4 py-16 sm:px-6"
      data-section-id="legal-page"
    >
      <h1 className="text-3xl font-bold text-ink-900">{document.title}</h1>
      <p className="mt-2 text-sm text-ink-500">
        {lastUpdatedLabel}: {lastUpdated}
      </p>
      {document.intro.map((paragraph) => (
        <p key={paragraph} className="mt-4 leading-7 text-ink-700">
          {paragraph}
        </p>
      ))}
      <nav
        aria-label={onThisPageLabel}
        className="mt-8 rounded-lg border border-brand-100 bg-brand-50 p-5"
      >
        <p className="text-sm font-semibold text-ink-900">{onThisPageLabel}</p>
        <ul className="mt-3 space-y-1.5 text-sm">
          {document.sections.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="text-brand-700 underline-offset-2 hover:underline"
              >
                {section.heading}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="mt-10 space-y-10">
        {document.sections.map((section) => (
          <LegalSectionBlock key={section.id} section={section} />
        ))}
      </div>
    </article>
  );
}
