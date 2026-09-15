import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const yaml = require('js-yaml') as {
  load: (input: string, options?: { schema?: unknown }) => unknown;
  DEFAULT_SCHEMA: unknown;
};
const jsYamlVersion = (
  require('js-yaml/package.json') as { version: string }
).version;

const appRoot = join(process.cwd());
const packageJson = JSON.parse(
  readFileSync(join(appRoot, 'package.json'), 'utf8'),
) as {
  overrides?: Record<string, string>;
};
const packageLock = JSON.parse(
  readFileSync(join(appRoot, 'package-lock.json'), 'utf8'),
) as {
  packages?: Record<string, { version?: string }>;
};

const JS_YAML_V3_MIN = '3.15.2';
const JS_YAML_V4_MIN = '4.3.2';

function parseVersion(version: string): number[] {
  return version.split('.').map((part) => Number.parseInt(part, 10));
}

function isAtLeast(version: string, minimum: string): boolean {
  const left = parseVersion(version);
  const right = parseVersion(minimum);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const a = left[index] ?? 0;
    const b = right[index] ?? 0;
    if (a > b) {
      return true;
    }
    if (a < b) {
      return false;
    }
  }
  return true;
}

function lockfileJsYamlVersions(): string[] {
  const packages = packageLock.packages ?? {};
  return Object.entries(packages)
    .filter(([path]) => path.endsWith('/js-yaml') || path === 'node_modules/js-yaml')
    .map(([, meta]) => meta.version)
    .filter((version): version is string => Boolean(version));
}

describe('js-yaml overrides (CVE-2026-84375)', () => {
  it('pins patched js-yaml releases in package.json overrides', () => {
    expect(packageJson.overrides?.['js-yaml@3']).toBe(JS_YAML_V3_MIN);
    expect(packageJson.overrides?.['js-yaml@4']).toBe(JS_YAML_V4_MIN);
  });

  it('resolves only patched js-yaml versions in the lockfile', () => {
    const versions = lockfileJsYamlVersions();
    expect(versions.length).toBeGreaterThan(0);
    for (const version of versions) {
      const minimum =
        version.startsWith('3.') ? JS_YAML_V3_MIN : JS_YAML_V4_MIN;
      expect(isAtLeast(version, minimum)).toBe(true);
    }
  });

  it('rejects abusive empty merge-key sequences within resource limits', () => {
    expect(isAtLeast(jsYamlVersion, JS_YAML_V4_MIN)).toBe(true);

    const mergeSourceCount = 500;
    const mergeTargetCount = 50;
    let document = 'a: &ref\n';
    for (let index = 0; index < mergeSourceCount; index += 1) {
      document += '- {}\n';
    }
    document += 'targets:\n';
    for (let index = 0; index < mergeTargetCount; index += 1) {
      document += `  t${index}:\n    <<: *ref\n`;
    }

    expect(() => yaml.load(document, { schema: yaml.DEFAULT_SCHEMA })).toThrow();
  });
});
