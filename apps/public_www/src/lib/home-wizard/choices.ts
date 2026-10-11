import choicesJson from '@/data/home_wizard_choices.json';

export interface WizardLabels {
  readonly en: string;
  readonly 'zh-HK': string;
}

export interface WizardActivityTypeOption {
  readonly id: string;
  readonly categoryId: string;
  readonly labels: WizardLabels;
}

export interface WizardAgeGroupOption {
  readonly id: string;
  readonly searchAge: number;
  readonly labels: WizardLabels;
}

export interface WizardRegionOption {
  readonly id: string;
  readonly areaId: string;
  readonly labels: WizardLabels;
}

export interface WizardNeighbourhoodOption {
  readonly id: string;
  readonly regionId: string;
  readonly district: string;
  readonly areaId: string;
  readonly labels: WizardLabels;
}

export interface HomeWizardChoices {
  readonly version: number;
  readonly activityTypes: readonly WizardActivityTypeOption[];
  readonly ageGroups: readonly WizardAgeGroupOption[];
  readonly regions: readonly WizardRegionOption[];
  readonly neighbourhoods: readonly WizardNeighbourhoodOption[];
}

export const homeWizardChoices = choicesJson as HomeWizardChoices;

export function neighbourhoodsForRegion(
  regionId: string | null,
): readonly WizardNeighbourhoodOption[] {
  if (!regionId) {
    return [];
  }
  return homeWizardChoices.neighbourhoods.filter(
    (entry) => entry.regionId === regionId,
  );
}

export function labelForLocale(
  labels: WizardLabels,
  locale: string,
): string {
  if (locale === 'zh-HK' && labels['zh-HK'].trim() !== '') {
    return labels['zh-HK'];
  }
  return labels.en;
}
