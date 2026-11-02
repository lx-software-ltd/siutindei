import { StaticLocaleRedirect } from '@/components/shared/static-locale-redirect';
import { DEFAULT_LOCALE } from '@/content/locales';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

const targetHref = localizePath(ROUTES.activity, DEFAULT_LOCALE);

export default function ActivityRedirectPage() {
  return (
    <StaticLocaleRedirect
      href={targetHref}
      message="Redirecting to the English activity page…"
      linkLabel="Continue to Activity"
    />
  );
}
