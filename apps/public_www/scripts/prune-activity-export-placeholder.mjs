// Next.js static export needs at least one [id] param. Production builds
// pass a placeholder, then this step removes those files so the published
// site has no fictional activity pages. Real listing ids are never this value.

import { existsSync, rmSync } from 'node:fs';
import path from 'node:path';

const PLACEHOLDER_ID = '__export_placeholder__';
const LOCALES = ['en', 'zh-HK'];
const outDir = path.resolve('out');

for (const locale of LOCALES) {
  const dir = path.join(outDir, locale, 'activity', PLACEHOLDER_ID);
  if (!existsSync(dir)) {
    continue;
  }
  rmSync(dir, { recursive: true, force: true });
  console.log(`Removed activity export placeholder ${locale}/activity/${PLACEHOLDER_ID}`);
}
