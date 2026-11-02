// Sets <html lang="..."> on each exported HTML file from its locale path segment
// (e.g. out/en/... → en, out/zh-HK/... → zh-HK).

import { promises as fs } from 'node:fs';
import path from 'node:path';

const OUT_DIR = process.env.PUBLIC_WWW_OUT_DIR
  ? path.resolve(process.env.PUBLIC_WWW_OUT_DIR)
  : path.resolve('out');
const SUPPORTED_LOCALES = new Set(['en', 'zh-HK']);
const DEFAULT_LANG = 'en';

function resolveLangFromOutPath(filePath) {
  const relative = path.relative(OUT_DIR, filePath);
  const firstSegment = relative.split(path.sep)[0] ?? '';
  if (SUPPORTED_LOCALES.has(firstSegment)) {
    return firstSegment;
  }

  return DEFAULT_LANG;
}

function setHtmlLangAttribute(html, lang) {
  if (/<html[^>]*\slang=/i.test(html)) {
    return html.replace(
      /(<html[^>]*)\slang="[^"]*"/i,
      `$1 lang="${lang}"`,
    );
  }

  return html.replace(/<html/i, `<html lang="${lang}"`);
}

async function* walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      yield fullPath;
    }
  }
}

async function patchFile(filePath) {
  const original = await fs.readFile(filePath, 'utf8');
  const lang = resolveLangFromOutPath(filePath);
  const updated = setHtmlLangAttribute(original, lang);
  if (updated === original) {
    return false;
  }

  await fs.writeFile(filePath, updated, 'utf8');
  return true;
}

async function main() {
  try {
    await fs.access(OUT_DIR);
  } catch {
    console.error(`Build output not found: ${OUT_DIR}`);
    process.exit(1);
  }

  let updatedCount = 0;
  let totalCount = 0;
  for await (const filePath of walk(OUT_DIR)) {
    totalCount += 1;
    const updated = await patchFile(filePath);
    if (updated) {
      updatedCount += 1;
    }
  }

  console.log(
    `lang:inject — ${updatedCount}/${totalCount} HTML files patched.`,
  );
}

main().catch((error) => {
  console.error('lang:inject failed:', error);
  process.exit(1);
});
