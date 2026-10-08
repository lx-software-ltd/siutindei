'use client';

import { Button } from '@/components/ui/button';

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error: _error, reset }: GlobalErrorProps) {
  return (
    <main className='mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-4 px-6 text-center'>
      <h1 className='text-xl font-semibold text-slate-900'>Something went wrong</h1>
      <p className='text-sm text-slate-600'>
        We could not load this page. Please try again.
      </p>
      <Button type='button' onClick={reset}>
        Try Again
      </Button>
    </main>
  );
}
