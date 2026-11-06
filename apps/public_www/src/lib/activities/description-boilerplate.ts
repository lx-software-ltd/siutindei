/** Import filler. Keep this phrase pair aligned with the API check. */
export const ENGLISH_IMPORT_BOILERPLATE = 'is a class or early-years centre in';

export const CANTONESE_IMPORT_BOILERPLATE = '幼兒或興趣班，適合小朋友同家庭';

export function descriptionIsImportBoilerplate(
  description: string | null | undefined,
): boolean {
  const text = description ?? '';
  return (
    text.includes(ENGLISH_IMPORT_BOILERPLATE) ||
    text.includes(CANTONESE_IMPORT_BOILERPLATE)
  );
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
