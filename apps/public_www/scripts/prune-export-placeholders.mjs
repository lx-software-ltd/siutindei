// Next.js static export needs at least one param for each dynamic route.
// With an empty catalogue the build passes a placeholder id, then this step
// removes those pages so the published site has no fictional activity or
// landing pages. Real ids and activity type slugs are never this value.

import { existsSync, rmSync } from 'node:fs';
import path from 'node:path';

const PLACEHOLDER_ID = '__export_placeholder__';
const LOCALES = ['en', 'zh-HK'];
const ROUTES = ['activity', 'activities'];
const outDir = path.resolve('out');

for (const locale of LOCALES) {
  for (const route of ROUTES) {
    const dir = path.join(outDir, locale, route, PLACEHOLDER_ID);
    if (!existsSync(dir)) {
      continue;
    }
    rmSync(dir, { recursive: true, force: true });
    console.log(`Removed export placeholder ${locale}/${route}/${PLACEHOLDER_ID}`);
  }
}
