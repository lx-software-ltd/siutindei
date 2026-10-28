import { getPublicWwwUrl } from '@/lib/config';

import { LegalLinks } from '../legal-links';

export function LoginFooter() {
  return (
    <footer className='border-t border-brand-100 bg-brand-50 text-ink-700'>
      <div className='mx-auto flex w-full max-w-3xl flex-col items-center gap-3 px-6 py-5 text-center text-xs sm:flex-row sm:justify-between sm:text-left'>
        <p>
          Looking for the public site?{' '}
          <a
            href={getPublicWwwUrl()}
            className='font-semibold text-brand-700 underline underline-offset-2'
          >
            Go to siutindei.com
          </a>
        </p>
        <LegalLinks className='whitespace-nowrap text-xs text-ink-700' />
      </div>
    </footer>
  );
}
