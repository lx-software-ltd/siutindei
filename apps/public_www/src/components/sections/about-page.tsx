import { formatContentTemplate } from '@/content/content-field-utils';
import type { AboutPageContent } from '@/content/types';
import {
  ArticlePage,
  type ArticleSection,
} from '@/components/sections/article-page';

const WRITE_TO_ME_SECTION_ID = 'write-to-me';

interface AboutPageProps {
  readonly content: AboutPageContent;
  readonly contactEmail: string;
  /** "Stanley, Hong Kong": the area the catalogue covers today. */
  readonly placeFull: string;
}

function sectionsWithContact(
  sections: AboutPageContent['sections'],
  contactEmail: string,
): readonly ArticleSection[] {
  const email = contactEmail.trim();
  if (email === '') {
    return sections;
  }

  return sections.map((section) => {
    if (section.id !== WRITE_TO_ME_SECTION_ID) {
      return section;
    }

    return {
      ...section,
      links: [{ href: `mailto:${email}`, label: email }],
    };
  });
}

function withPlace(text: string, placeFull: string): string {
  return formatContentTemplate(text, { placeFull });
}

export function AboutPage({ content, contactEmail, placeFull }: AboutPageProps) {
  const summary: ArticleSection = {
    ...content.summary,
    paragraphs: content.summary.paragraphs.map((paragraph) => withPlace(paragraph, placeFull)),
  };
  const questions: ArticleSection = {
    id: content.questions.id,
    heading: content.questions.heading,
    paragraphs: [],
    questions: content.questions.items.map((item) => ({
      question: item.question,
      answer: withPlace(item.answer, placeFull),
    })),
  };
  return (
    <ArticlePage
      title={content.title}
      intro={content.intro}
      sections={[
        summary,
        ...sectionsWithContact(content.sections, contactEmail),
        questions,
      ]}
      onThisPageLabel={content.onThisPageLabel}
      sectionId="about-page"
    />
  );
}
