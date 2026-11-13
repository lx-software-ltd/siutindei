import type { Metadata } from 'next';

import { MinimalStatusChrome } from '@/components/shared/minimal-status-chrome';
import enContent from '@/content/en.json';
import { getSiteConfig } from '@/lib/site-config';

const notFoundCopy = enContent.common.errors.notFound;

export const metadata: Metadata = {
  title: `${notFoundCopy.title} · ${getSiteConfig().siteName}`,
  description: notFoundCopy.description,
};

export default function NotFound() {
  return <MinimalStatusChrome variant="notFound" />;
}
