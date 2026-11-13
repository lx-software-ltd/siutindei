export interface ArticleLink {
  readonly href: string;
  readonly label: string;
}

export interface ArticleSection {
  readonly id: string;
  readonly heading: string;
  readonly paragraphs: readonly string[];
  readonly bullets?: readonly string[];
  readonly links?: readonly ArticleLink[];
}

interface ArticlePageProps {
  readonly title: string;
  readonly intro: readonly string[];
  readonly sections: readonly ArticleSection[];
  readonly onThisPageLabel: string;
  readonly meta?: string;
  readonly sectionId: string;
}

function ArticleSectionBlock({ section }: { readonly section: ArticleSection }) {
  const bullets = section.bullets ?? [];
  const links = section.links ?? [];

  return (
    <section id={section.id} className="scroll-mt-24">
      <h2 className="text-xl font-semibold text-ink-900">{section.heading}</h2>
      {section.paragraphs.map((paragraph) => (
        <p key={paragraph} className="mt-3 leading-7 text-ink-700">
          {paragraph}
        </p>
      ))}
      {bullets.length > 0 ? (
        <ul className="mt-3 list-disc space-y-2 pl-6 leading-7 text-ink-700">
          {bullets.map((bullet) => (
            <li key={bullet}>{bullet}</li>
          ))}
        </ul>
      ) : null}
      {links.map((link) => (
        <p key={link.href} className="mt-3 leading-7">
          <a
            href={link.href}
            className="link-underlined"
          >
            {link.label}
          </a>
        </p>
      ))}
    </section>
  );
}

export function ArticlePage({
  title,
  intro,
  sections,
  onThisPageLabel,
  meta,
  sectionId,
}: ArticlePageProps) {
  return (
    <article
      className="mx-auto max-w-3xl px-4 py-16 sm:px-6"
      data-section-id={sectionId}
    >
      <h1 className="text-3xl font-bold text-ink-900">{title}</h1>
      {meta ? <p className="mt-2 text-sm text-ink-500">{meta}</p> : null}
      {intro.map((paragraph) => (
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
          {sections.map((section) => (
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
        {sections.map((section) => (
          <ArticleSectionBlock key={section.id} section={section} />
        ))}
      </div>
    </article>
  );
}
