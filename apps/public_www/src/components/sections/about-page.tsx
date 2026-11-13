import type { AboutPageContent } from '@/content/types';
import {
  ArticlePage,
  type ArticleSection,
} from '@/components/sections/article-page';

const WRITE_TO_ME_SECTION_ID = 'write-to-me';

interface AboutPageProps {
  readonly content: AboutPageContent;
  readonly contactEmail: string;
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

export function AboutPage({ content, contactEmail }: AboutPageProps) {
  return (
    <ArticlePage
      title={content.title}
      intro={content.intro}
      sections={sectionsWithContact(content.sections, contactEmail)}
      onThisPageLabel={content.onThisPageLabel}
      sectionId="about-page"
    />
  );
}
