'use client';

import { MinimalStatusChrome } from '@/components/shared/minimal-status-chrome';

interface RootErrorPageProps {
  readonly reset: () => void;
}

export default function RootErrorPage({ reset }: RootErrorPageProps) {
  return <MinimalStatusChrome variant="serverError" onRetry={reset} />;
}
