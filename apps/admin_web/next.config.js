const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
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
