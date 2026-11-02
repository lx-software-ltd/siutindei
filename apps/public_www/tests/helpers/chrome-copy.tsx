import type { ReactNode } from 'react';

import {
  ChromeCopyProvider,
  type ChromeCopy,
} from '@/components/shared/chrome-copy';
import { getContent } from '@/content';
import type { Locale } from '@/content/locales';

function chromeCopyFor(locale: Locale): ChromeCopy {
  const content = getContent(locale);
  return {
    consent: content.common.consent,
    notFound: content.common.errors.notFound,
    serverError: content.common.errors.serverError,
    temporarilyClosedLabel: content.searchPage.temporarilyClosedLabel,
  };
}

export function withChromeCopy(children: ReactNode) {
  return (
    <ChromeCopyProvider
      copy={{
        en: chromeCopyFor('en'),
        'zh-HK': chromeCopyFor('zh-HK'),
      }}
    >
      {children}
    </ChromeCopyProvider>
  );
}
