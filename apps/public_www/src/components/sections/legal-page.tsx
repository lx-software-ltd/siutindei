import type { LegalContent } from '@/content/types';
import { ArticlePage } from '@/components/sections/article-page';

type LegalDocument = LegalContent['privacy'];

interface LegalPageProps {
  readonly document: LegalDocument;
  readonly lastUpdatedLabel: LegalContent['lastUpdatedLabel'];
  readonly lastUpdated: LegalContent['lastUpdated'];
  readonly onThisPageLabel: LegalContent['onThisPageLabel'];
}

export function LegalPage({
  document,
  lastUpdatedLabel,
  lastUpdated,
  onThisPageLabel,
}: LegalPageProps) {
  return (
    <ArticlePage
      title={document.title}
      intro={document.intro}
      sections={document.sections}
      onThisPageLabel={onThisPageLabel}
      meta={`${lastUpdatedLabel}: ${lastUpdated}`}
      sectionId="legal-page"
    />
  );
}
