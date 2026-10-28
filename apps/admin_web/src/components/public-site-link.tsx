import { getPublicWwwUrl } from '@/lib/config';

/** Shared exit to the public site. A new tab keeps an open admin draft. */
export function PublicSiteLink() {
  return (
    <a
      href={getPublicWwwUrl()}
      target='_blank'
      rel='noreferrer noopener'
      className='admin-focus font-semibold text-brand-700 underline underline-offset-2'
    >
      Go to siutindei.com
    </a>
  );
}
