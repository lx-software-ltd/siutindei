import { StaticLocaleRedirect } from '@/components/shared/static-locale-redirect';
import { DEFAULT_LOCALE } from '@/content/locales';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

const targetHref = localizePath(ROUTES.terms, DEFAULT_LOCALE);

export default function TermsRedirectPage() {
  return (
    <StaticLocaleRedirect
      href={targetHref}
      message="Redirecting to the English terms page…"
      linkLabel="Continue to Terms"
    />
  );
}
