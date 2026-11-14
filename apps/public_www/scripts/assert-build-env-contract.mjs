/**
 * Fails the build when required NEXT_PUBLIC_* variables for the public website
 * are missing or empty. Keep this list in sync with:
 *   apps/public_www/build-env.defaults.json
 *   scripts/deploy/resolve-public-www-build-env.sh
 *   .github/workflows/deploy-public-www.yml  (assert + build env blocks)
 *   .github/workflows/promote-public-www.yml (build env block)
 */
const REQUIRED = ['NEXT_PUBLIC_SITE_ORIGIN', 'NEXT_PUBLIC_SITE_NAME'];

const SEARCH_API_REQUIRED = [
  'NEXT_PUBLIC_SEARCH_API_KEY',
  'NEXT_PUBLIC_DEVICE_ATTESTATION_TOKEN',
];

const RECOMMENDED = [
  'NEXT_PUBLIC_SITE_TAGLINE',
  'NEXT_PUBLIC_BUILD_YEAR',
  'NEXT_PUBLIC_EMAIL',
];

// Optional build-time inputs. Not required for a valid build, but listed
// here so the contract enumerates every NEXT_PUBLIC_* variable the static
// export depends on (per .cursorrules). Their set/unset status is logged
// for deploy-run auditability.
const OPTIONAL = [
  'NEXT_PUBLIC_WHATSAPP_URL',
  'NEXT_PUBLIC_INSTAGRAM_URL',
  'NEXT_PUBLIC_FACEBOOK_URL',
  'NEXT_PUBLIC_STAGING_BADGE_ENABLED',
  'NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED',
  'NEXT_PUBLIC_STAGING_SEARCH_FIXTURE_URL',
  'NEXT_PUBLIC_SEARCH_API_BASE_URL',
  'NEXT_PUBLIC_GOOGLE_MAPS_API_KEY',
  'NEXT_PUBLIC_GTM_ID',
  'NEXT_PUBLIC_GTM_ALLOWED_HOSTS',
  'NEXT_PUBLIC_META_PIXEL_ID',
  'NEXT_PUBLIC_META_PIXEL_ALLOWED_HOSTS',
  'NEXT_PUBLIC_SEARCH_AREA_SCOPE',
];

function readBooleanEnv(name) {
  const raw = (process.env[name] ?? '').trim().toLowerCase();
  return raw === 'true' || raw === '1' || raw === 'yes';
}

function isMissing(name) {
  return (process.env[name] ?? '').trim() === '';
}

let failed = false;

for (const name of REQUIRED) {
  if (isMissing(name)) {
    console.error(`Missing or empty required env: ${name}`);
    failed = true;
  }
}

const stagingFixtureEnabled = readBooleanEnv(
  'NEXT_PUBLIC_STAGING_SEARCH_DATA_ENABLED',
);

if (!stagingFixtureEnabled) {
  for (const name of SEARCH_API_REQUIRED) {
    if (isMissing(name)) {
      console.error(
        `Missing or empty required env (live search): ${name}`,
      );
      failed = true;
    }
  }
}

for (const name of RECOMMENDED) {
  if (isMissing(name)) {
    console.warn(`Recommended env is empty: ${name}`);
  }
}

for (const name of OPTIONAL) {
  console.log(`Optional env ${name}: ${isMissing(name) ? 'unset' : 'set'}`);
}

if (failed) {
  process.exit(1);
}
