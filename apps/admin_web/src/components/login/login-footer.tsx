import { LegalLinks } from '../legal-links';
import { PublicSiteLink } from '../public-site-link';

export function LoginFooter() {
  return (
    <footer className='border-t border-brand-100 bg-brand-50 text-ink-700'>
      <div className='mx-auto flex w-full max-w-3xl flex-col items-center gap-3 px-6 py-5 text-center text-xs sm:flex-row sm:justify-between sm:text-left'>
        <p>
          Looking for the public site? <PublicSiteLink />
        </p>
        <LegalLinks className='whitespace-nowrap text-xs text-ink-700' />
      </div>
    </footer>
  );
}
