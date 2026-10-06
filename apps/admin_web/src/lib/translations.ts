export const translationLanguages = [
  { code: 'zh', label: 'Chinese (zh)' },
  { code: 'yue', label: 'Cantonese (yue)' },
] as const;

export type TranslationLanguageCode =
  (typeof translationLanguages)[number]['code'];

export const languageOptions = [
  { code: 'en', label: 'English (en)', flagSrc: '/flags/gb.png' },
  { code: 'zh', label: 'Chinese (zh)', flagSrc: '/flags/cn.png' },
  { code: 'yue', label: 'Cantonese (yue)', flagSrc: '/flags/hk.png' },
] as const;

export type LanguageCode = (typeof languageOptions)[number]['code'];

export function emptyTranslations(): Record<TranslationLanguageCode, string> {
  return {
    zh: '',
    yue: '',
  };
}

export function extractTranslations(
  translations?: Record<string, string> | null
): Record<TranslationLanguageCode, string> {
  return {
    zh: translations?.zh ?? '',
    yue: translations?.yue ?? '',
  };
}

export function buildTranslationsPayload(
  translations: Record<TranslationLanguageCode, string>
): Record<string, string> {
  const payload: Record<string, string> = {};
  for (const { code } of translationLanguages) {
    const value = translations[code].trim();
    if (value) {
      payload[code] = value;
    }
  }
  return payload;
}

const formTranslationCodes = new Set<string>(['en', 'zh', 'yue']);

export function mergePreservedTranslations(
  payload: Record<string, string>,
  existing?: Record<string, string> | null
): Record<string, string> {
  const merged = { ...payload };
  if (!existing) {
    return merged;
  }
  for (const [code, value] of Object.entries(existing)) {
    if (formTranslationCodes.has(code)) {
      continue;
    }
    if (typeof value === 'string' && value.trim()) {
      merged[code] = value;
    }
  }
  return merged;
}
