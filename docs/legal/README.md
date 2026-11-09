# Legal documents

## Canonical source

The public website is the single canonical host for all legal documents.
Every other surface links to it instead of embedding its own copy:

| Document | Canonical URL | Source of the text |
|---|---|---|
| Privacy Policy (incl. PICS) | `https://siutindei.com/privacy` | `apps/public_www/src/content/legal/en.json` + `zh-HK.json` → `privacy` |
| Terms of Use (incl. manager/listing terms) | `https://siutindei.com/terms` | same files → `terms` |

Rendering component: `apps/public_www/src/components/sections/legal-page.tsx`.

Surfaces that link to the canonical pages:

- Flutter app: login screen legal notice
  (`apps/siutindei_app/lib/features/auth/screens/login_screen.dart`, URLs in
  `lib/config/site_links.dart`, overridable via
  `--dart-define=PUBLIC_WWW_BASE_URL=...`).
- Admin web: login screen and dashboard footer
  (`apps/admin_web/src/components/legal-links.tsx`, base URL from
  `NEXT_PUBLIC_PUBLIC_WWW_URL`, defaults to the production website).
- Store listings: privacy policy URL fields in Google Play Console and App
  Store Connect must point at the canonical privacy URL (see
  `store-disclosures.md`).

## Key facts encoded in the documents

- Legal entity: LX Software, a sole proprietorship registered in Hong Kong.
- Data access / correction contact: `support@siutindei.com`.
- Hosting: AWS Singapore (`ap-southeast-1`); the privacy policy therefore
  discloses cross-border transfer outside Hong Kong.
- Applicable law: Personal Data (Privacy) Ordinance (Cap. 486), HKSAR
  governing law for the terms.
- Analytics (GTM, Meta Pixel) are opt-in via the website consent banner;
  the privacy policy's cookies section (`/privacy#cookies`) describes this.

## Update procedure

1. Edit `privacy` / `terms` in **both**
   `apps/public_www/src/content/legal/en.json` and `zh-HK.json`. The two
   locales must keep identical section `id` lists (enforced by
   `apps/public_www/tests/lib/legal-content.test.ts`).
2. Bump `lastUpdated` in both locale files.
3. If data practices changed (new processor, new data category, new
   retention rule), update `store-disclosures.md` and re-submit the Play
   Data Safety form / App Store privacy answers.
4. Deploy: the pages ship with the normal public-www staging deploy +
   production promote flow.

Anchored sections that other code links to (do not rename the ids):

- `/privacy#cookies` — linked from the analytics consent banner.
- `/privacy#pics` — Personal Information Collection Statement, suitable for
  linking near any form that collects personal data.
