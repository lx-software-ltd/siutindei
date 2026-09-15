import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../..',
);

const requireFromRoot = createRequire(
  path.join(packageRoot, 'package.json'),
);

describe('js-yaml CVE-2026-84375 (3.x override)', () => {
  it('pins js-yaml@3 to 3.15.2 in package overrides', () => {
    const pkg = JSON.parse(
      readFileSync(path.join(packageRoot, 'package.json'), 'utf8'),
    ) as { overrides?: Record<string, string> };
    expect(pkg.overrides?.['js-yaml@3']).toBe('3.15.2');
  });

  it('locks every js-yaml 3.x install to 3.15.2', () => {
    const lock = JSON.parse(
      readFileSync(path.join(packageRoot, 'package-lock.json'), 'utf8'),
    ) as {
      packages?: Record<string, { version?: string }>;
    };
    const packages = lock.packages ?? {};
    for (const [name, meta] of Object.entries(packages)) {
      if (!name.endsWith('/js-yaml') && name !== 'node_modules/js-yaml') {
        continue;
      }
      const version = meta.version ?? '';
      if (!version.startsWith('3.')) {
        continue;
      }
      expect(version).toBe('3.15.2');
    }
  });

  it('rejects pathological empty merge sources within maxTotalMergeKeys', () => {
    const yaml = requireFromRoot(
      '@lhci/utils/node_modules/js-yaml',
    ) as {
      load: (src: string) => unknown;
    };
    const n = 200;
    const src =
      `arr: &arr [${'{},'.repeat(n).slice(0, -1)}]\n` +
      `targets:\n${'  - <<: *arr\n'.repeat(n)}`;
    const start = Date.now();
    expect(() => yaml.load(src)).toThrow();
    expect(Date.now() - start).toBeLessThan(5000);
  });
});
