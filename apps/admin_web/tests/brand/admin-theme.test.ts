import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

function themeDeclarations(css: string): Map<string, string> {
  const start = css.indexOf('@theme');
  const open = css.indexOf('{', start);
  let depth = 0;
  let end = open;
  for (let index = open; index < css.length; index += 1) {
    if (css[index] === '{') {
      depth += 1;
    } else if (css[index] === '}') {
      depth -= 1;
      if (depth === 0) {
        end = index;
        break;
      }
    }
  }
  const body = css.slice(open + 1, end);
  const decls = new Map<string, string>();
  for (const match of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    decls.set(match[1], match[2].replace(/\s+/g, ' ').trim());
  }
  return decls;
}

describe('admin brand tokens', () => {
  it('mirrors the public colour and font tokens', () => {
    const root = resolve(__dirname, '../../../..');
    const admin = themeDeclarations(
      readFileSync(resolve(root, 'apps/admin_web/src/app/globals.css'), 'utf8')
    );
    const pub = themeDeclarations(
      readFileSync(resolve(root, 'apps/public_www/src/app/globals.css'), 'utf8')
    );

    for (const [name, value] of pub) {
      if (name.startsWith('--color-') || name.startsWith('--font-')) {
        expect(admin.get(name), name).toBe(value);
      }
    }
  });
});
