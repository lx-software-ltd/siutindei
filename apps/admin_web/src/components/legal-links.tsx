import { getPrivacyPolicyUrl, getTermsOfUseUrl } from '../lib/config';

interface LegalLinksProps {
  className?: string;
}

export function LegalLinks({ className }: LegalLinksProps) {
  return (
    <p className={className ?? 'text-center text-xs text-ink-700'}>
      <a
        href={getPrivacyPolicyUrl()}
        target='_blank'
        rel='noreferrer noopener'
        className='underline underline-offset-2 hover:text-brand-600'
      >
        Privacy Policy
      </a>
      <span className='mx-2' aria-hidden='true'>
        ·
      </span>
      <a
        href={getTermsOfUseUrl()}
        target='_blank'
        rel='noreferrer noopener'
        className='underline underline-offset-2 hover:text-brand-600'
      >
        Terms of Use
      </a>
    </p>
  );
}
