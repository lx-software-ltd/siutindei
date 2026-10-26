import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);

const PATCHED_LAUNCH_EDITOR = '2.14.2';

describe('launch-editor GHSA-587h-7wmj-h5pm / GHSA-698v-4r3x-3vcv', () => {
  it('pins launch-editor in package overrides', () => {
    const pkg = JSON.parse(
      readFileSync(path.join(packageRoot, 'package.json'), 'utf8'),
    ) as { overrides?: Record<string, string> };
    expect(pkg.overrides?.['launch-editor']).toBe(PATCHED_LAUNCH_EDITOR);
  });

  it('locks every launch-editor install to the patched release', () => {
    const lock = JSON.parse(
      readFileSync(path.join(packageRoot, 'package-lock.json'), 'utf8'),
    ) as {
      packages?: Record<string, { version?: string }>;
    };
    const packages = lock.packages ?? {};
    for (const [name, meta] of Object.entries(packages)) {
      if (
        !name.endsWith('/launch-editor') &&
        name !== 'node_modules/launch-editor'
      ) {
        continue;
      }
      expect(meta.version).toBe(PATCHED_LAUNCH_EDITOR);
    }
  });
});
