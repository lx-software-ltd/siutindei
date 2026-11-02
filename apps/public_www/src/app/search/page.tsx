import { StaticLocaleRedirect } from '@/components/shared/static-locale-redirect';
import { DEFAULT_LOCALE } from '@/content/locales';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

const targetHref = localizePath(ROUTES.search, DEFAULT_LOCALE);

export default function SearchRedirectPage() {
  return (
    <StaticLocaleRedirect
      href={targetHref}
      message="Redirecting to the English search page…"
      linkLabel="Continue to Search"
    />
  );
}
