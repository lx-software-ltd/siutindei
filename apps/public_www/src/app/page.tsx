import { StaticLocaleRedirect } from '@/components/shared/static-locale-redirect';
import { DEFAULT_LOCALE } from '@/content/locales';
import { localizePath } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

// Production CloudFront redirects `/` to a locale before this shell is served.
// The shell stays for local static hosting (`npx serve out`).
const targetHref = localizePath(ROUTES.home, DEFAULT_LOCALE);

export default function RootPage() {
  return (
    <StaticLocaleRedirect
      href={targetHref}
      message="Redirecting to the English homepage…"
      linkLabel="Continue to Siu Tin Dei"
    />
  );
}
