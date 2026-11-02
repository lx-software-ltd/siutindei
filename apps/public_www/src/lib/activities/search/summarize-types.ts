import type { Locale } from '@/content/locales';
import { homeWizardChoices, labelForLocale } from '@/lib/home-wizard/choices';

export function summarizeTypes(
  locale: Locale,
  typeIds: readonly string[],
): string {
  const typeLabels = typeIds
    .map((id) => {
      const match = homeWizardChoices.activityTypes.find(
        (entry) => entry.id === id,
      );
      return match ? labelForLocale(match.labels, locale) : null;
    })
    .filter((value): value is string => Boolean(value));
  if (typeLabels.length === 0) {
    return '';
  }
  if (typeLabels.length === 1) {
    return typeLabels[0] ?? '';
  }
  return `${typeLabels[0]} +${typeLabels.length - 1}`;
}
