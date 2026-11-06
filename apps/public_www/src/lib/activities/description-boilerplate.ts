/** Import filler. Keep this phrase pair aligned with the API check. */
export const ENGLISH_IMPORT_BOILERPLATE = 'for children and families';

export const CANTONESE_IMPORT_BOILERPLATE = '適合小朋友同家庭';

export const ENGLISH_IMPORT_STEMS = ['is a ', 'is an '] as const;

export function descriptionIsImportBoilerplate(
  description: string | null | undefined,
): boolean {
  const text = description ?? '';
  if (text.includes(CANTONESE_IMPORT_BOILERPLATE)) {
    return true;
  }
  if (!text.includes(ENGLISH_IMPORT_BOILERPLATE)) {
    return false;
  }
  return ENGLISH_IMPORT_STEMS.some((stem) => text.includes(stem));
}

/** Blank or filler copy on a template organization stays off the public page. */
export function hideImportTemplateCopy(
  descriptionSource: string | null | undefined,
  description: string | null | undefined,
): boolean {
  if (descriptionSource !== 'template') {
    return false;
  }
  const text = (description ?? '').trim();
  if (text === '') {
    return true;
  }
  return descriptionIsImportBoilerplate(text);
}
