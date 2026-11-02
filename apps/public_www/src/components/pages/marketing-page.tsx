import type { Locale } from '@/content/locales';
import type { PageBodyGridConfig, SiteContent } from '@/content/types';
import { PageBodyGrid } from '@/components/sections/grid/page-body-grid';

interface MarketingPageProps {
  readonly locale: Locale;
  readonly content: SiteContent;
  readonly body: PageBodyGridConfig;
}

export function MarketingPage({ locale, content, body }: MarketingPageProps) {
  return <PageBodyGrid locale={locale} content={content} body={body} />;
}
