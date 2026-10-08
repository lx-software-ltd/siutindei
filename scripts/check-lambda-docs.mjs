#!/usr/bin/env node
/**
 * Every createPythonFunction id under backend/infrastructure/lib must be
 * named in docs/architecture/lambdas.md.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const root = join(import.meta.dirname, '..');
const libDir = join(root, 'backend', 'infrastructure', 'lib');
const catalog = readFileSync(
  join(root, 'docs', 'architecture', 'lambdas.md'),
  'utf8',
);

function walk(dir) {
  const files = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      files.push(...walk(path));
    } else if (name.endsWith('.ts')) {
      files.push(path);
    }
  }
  return files;
}

const pattern = /createPythonFunction\(\s*["']([A-Za-z0-9]+)["']/g;
const missing = [];
for (const file of walk(libDir)) {
  const text = readFileSync(file, 'utf8');
  for (const match of text.matchAll(pattern)) {
    const id = match[1];
    if (!catalog.includes(id)) {
      missing.push(`${relative(root, file)}: ${id}`);
    }
  }
}

if (missing.length > 0) {
  console.error('Lambda docs check failed:');
  for (const item of missing) {
    console.error(`- ${item} is missing from docs/architecture/lambdas.md`);
  }
  process.exit(1);
}
console.log('Lambda docs check passed.');
