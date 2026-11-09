import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type { NextConfig } from 'next';

const appDir = path.dirname(fileURLToPath(import.meta.url));

const buildYear = String(
  process.env.NEXT_PUBLIC_BUILD_YEAR ?? new Date().getFullYear(),
);

const nextConfig: NextConfig = {
  output: 'export',
  // Monorepo root. Turbopack uses this instead of guessing from lockfiles.
  turbopack: {
    root: path.join(appDir, '../..'),
  },
  trailingSlash: true,
  reactStrictMode: true,
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_BUILD_YEAR: buildYear,
  },
  images: {
    unoptimized: true,
  },
  devIndicators: {
    position: 'bottom-right',
  },
};

export default nextConfig;
