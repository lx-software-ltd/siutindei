'use client';

import { createContext, useContext, type ReactNode } from 'react';

import type { Locale } from '@/content/locales';

export interface ChromeCopy {
  readonly consent: {
    readonly message: string;
    readonly privacyLinkLabel: string;
    readonly acceptLabel: string;
    readonly declineLabel: string;
  };
  readonly notFound: {
    readonly code: string;
    readonly title: string;
    readonly description: string;
    readonly homeLabel: string;
  };
  readonly serverError: {
    readonly code: string;
    readonly title: string;
    readonly description: string;
    readonly retryLabel: string;
  };
  readonly temporarilyClosedLabel: string;
}

const ChromeCopyContext = createContext<Readonly<Record<Locale, ChromeCopy>> | null>(
  null,
);

export function ChromeCopyProvider({
  copy,
  children,
}: {
  readonly copy: Readonly<Record<Locale, ChromeCopy>>;
  readonly children: ReactNode;
}) {
  return (
    <ChromeCopyContext.Provider value={copy}>{children}</ChromeCopyContext.Provider>
  );
}

export function useChromeCopy(locale: Locale): ChromeCopy {
  const copy = useContext(ChromeCopyContext);
  if (!copy) {
    throw new Error('ChromeCopyProvider is missing.');
  }
  return copy[locale];
}
