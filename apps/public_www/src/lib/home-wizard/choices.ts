import choicesJson from '@/data/home_wizard_choices.json';

export interface WizardLabels {
  readonly en: string;
  readonly 'zh-HK': string;
}

export interface WizardKindOption {
  readonly id: string;
  readonly labels: WizardLabels;
  readonly hint: WizardLabels;
  readonly hasTopics: boolean;
  /** A pilot kind is offered only once the catalogue has enough listings. */
  readonly pilot: boolean;
}

export interface WizardActivityTypeOption {
  readonly id: string;
  readonly categoryId: string;
  readonly labels: WizardLabels;
}

export interface WizardAgeGroupOption {
  readonly id: string;
  readonly searchAge: number;
  readonly minAge: number;
  readonly maxAge: number;
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
  readonly kinds: readonly WizardKindOption[];
  readonly activityTypes: readonly WizardActivityTypeOption[];
  readonly ageGroups: readonly WizardAgeGroupOption[];
  readonly regions: readonly WizardRegionOption[];
  readonly neighbourhoods: readonly WizardNeighbourhoodOption[];
}

export const homeWizardChoices = choicesJson as HomeWizardChoices;

/** Kinds the wizard and the results page offer. Pilot kinds wait. */
export const OFFERED_KINDS: readonly WizardKindOption[] = homeWizardChoices.kinds.filter(
  (kind) => !kind.pilot,
);

export const DEFAULT_SEARCH_KINDS: readonly string[] = OFFERED_KINDS.map(
  (kind) => kind.id,
);

/**
 * The kinds to offer once the build knows which pilot kinds have enough
 * listings. `pilotKindIds` comes from the catalogue at build time.
 */
export function offeredKinds(pilotKindIds: readonly string[]): readonly WizardKindOption[] {
  return homeWizardChoices.kinds.filter(
    (kind) => !kind.pilot || pilotKindIds.includes(kind.id),
  );
}

/** The offered topics, plus any already picked so a shared link can be unpicked. */
export function topicsToShow(
  offeredTopicIds: readonly string[],
  selectedIds: readonly string[],
): readonly WizardActivityTypeOption[] {
  return homeWizardChoices.activityTypes.filter(
    (type) => offeredTopicIds.includes(type.id) || selectedIds.includes(type.id),
  );
}

/** Any kind in the choices file, pilot or not, so a shared link still parses. */
export function kindOption(kindId: string | null | undefined): WizardKindOption | undefined {
  return homeWizardChoices.kinds.find((kind) => kind.id === kindId);
}

export const REGIONS_BY_ID: ReadonlyMap<string, WizardRegionOption> = new Map(
  homeWizardChoices.regions.map((region) => [region.id, region]),
);

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
