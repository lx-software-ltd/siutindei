const path = require('path');

/**
 * GitHub variable `SEARCH_AREA_SCOPE`, inlined for the Catalog filter.
 * A non-empty GitHub name wins over `NEXT_PUBLIC_SEARCH_AREA_SCOPE`.
 */
function searchAreaScope() {
  const named = process.env.SEARCH_AREA_SCOPE;
  if (typeof named === 'string' && named.trim() !== '') {
    return named.trim();
  }
  return (process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE ?? '').trim();
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_SEARCH_AREA_SCOPE: searchAreaScope(),
  },
  output: 'export',
  // Confirm the monorepo root so Next does not warn about both lockfiles.
  outputFileTracingRoot: path.join(__dirname, '../..'),
  trailingSlash: true,
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
