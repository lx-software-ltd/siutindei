'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';

import type { Locale } from '@/content/locales';
import type { SiteContent } from '@/content/types';
import { Button } from '@/components/shared/ui/button';
import { ChoiceTile } from '@/components/shared/ui/choice-tile';
import { Modal } from '@/components/shared/ui/modal';
import { useOfferedKinds, useOfferedTopicIds } from '@/components/shared/offered-kinds';
import { useSearchContext } from '@/components/shared/search/search-context';
import { formatContentTemplate } from '@/content/content-field-utils';
import { saveRecentSearch } from '@/lib/activities/recent-storage';
import {
  isWeekendPreset,
  kindHasTopics,
  toggleActivityTypeId,
  withKind,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import {
  allowedNeighbourhoodsForRegion,
  getConfiguredSearchAreaScope,
  isAllAreasSelectable,
  isRegionSelectable,
  openRegions,
  showsNeighbourhoodChoices,
  withDefaultOpenLocation,
  withoutImpliedOpenLocation,
} from '@/lib/home-wizard/area-scope';
import {
  homeWizardChoices,
  labelForLocale,
  REGIONS_BY_ID,
  topicsToShow,
} from '@/lib/home-wizard/choices';
import {
  ALL_HONG_KONG_ICON_SRC,
  REGION_ROW_ORDER,
  iconSrcForActivity,
  iconSrcForAge,
  iconSrcForKind,
  iconSrcForRegion,
  WEEKEND_ICON_SRC,
} from '@/lib/home-wizard/choice-icons';

function regionLabel(regionId: string | null, locale: Locale): string {
  const region = homeWizardChoices.regions.find((entry) => entry.id === regionId);
  return region ? labelForLocale(region.labels, locale) : '';
}

function neighbourhoodButtonClass(isSelected: boolean): string {
  const selected = isSelected
    ? 'border-accent-500 bg-brand-50'
    : 'border-brand-100 bg-white hover:border-brand-200';
  return (
    'min-h-11 rounded-full border px-4 py-2 text-sm font-semibold text-ink-900 ' +
    selected
  );
}

type NavigatorStep = 'location' | 'neighbourhood' | 'kind' | 'age' | 'activity';


function showsTopicStep(filters: SearchFiltersState): boolean {
  return Boolean(filters.kind) && kindHasTopics(filters.kind);
}

function stepsFor(
  regionId: string | null,
  filters: SearchFiltersState,
): readonly NavigatorStep[] {
  const steps: NavigatorStep[] = ['location'];
  if (showsNeighbourhoodChoices(regionId)) {
    steps.push('neighbourhood');
  }
  steps.push('kind', 'age');
  if (showsTopicStep(filters) || !(filters.kind || isWeekendPreset(filters))) {
    steps.push('activity');
  }
  return steps;
}

const EMPTY_NAVIGATOR_FILTERS: SearchFiltersState = {
  ageGroupId: null,
  regionId: null,
  neighbourhoodId: null,
  activityTypeIds: [],
  textQuery: '',
};

interface SearchNavigatorProps {
  readonly locale: Locale;
  readonly copy: SiteContent['smallWorld']['navigator'];
}

function stepIndex(
  step: NavigatorStep,
  regionId: string | null,
  filters: SearchFiltersState,
): number {
  return stepsFor(regionId, filters).indexOf(step) + 1;
}

export function SearchNavigator({ locale, copy }: SearchNavigatorProps) {
  const router = useRouter();
  const { setFilters } = useSearchContext();
  const offeredKinds = useOfferedKinds();
  const offeredTopicIds = useOfferedTopicIds();
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<NavigatorStep>('location');
  const [hasSelectedLocation, setHasSelectedLocation] = useState(false);
  const [draft, setDraft] = useState<SearchFiltersState>(
    EMPTY_NAVIGATOR_FILTERS,
  );

  const resetNavigator = useCallback(() => {
    const next = withDefaultOpenLocation(EMPTY_NAVIGATOR_FILTERS);
    setStep('location');
    setHasSelectedLocation(next.regionId !== null);
    setDraft(next);
  }, []);

  const closeNavigator = useCallback(() => {
    setIsOpen(false);
    resetNavigator();
  }, [resetNavigator]);

  function openNavigator() {
    resetNavigator();
    setIsOpen(true);
  }

  function selectLocation(regionId: string | null) {
    const allowed = regionId ? allowedNeighbourhoodsForRegion(regionId) : [];
    setDraft((current) => ({
      ...current,
      regionId,
      neighbourhoodId: allowed.length === 1 ? allowed[0].id : null,
    }));
    setHasSelectedLocation(true);
    setStep(showsNeighbourhoodChoices(regionId) ? 'neighbourhood' : 'kind');
  }

  function selectNeighbourhood(neighbourhoodId: string | null) {
    setDraft((current) => ({ ...current, neighbourhoodId }));
    setStep('kind');
  }

  function selectKind(kind: string) {
    setDraft((current) => ({ ...withKind(current, kind), day: null }));
    setStep('age');
  }

  function selectWeekend() {
    setDraft((current) => ({ ...withKind(current, null), day: 'weekend' }));
    setStep('age');
  }

  function selectAge(ageGroupId: string) {
    const next = { ...draft, ageGroupId };
    setDraft(next);
    if (showsTopicStep(next)) {
      setStep('activity');
      return;
    }
    submit(next);
  }

  function toggleType(typeId: string) {
    setDraft((current) => toggleActivityTypeId(current, typeId));
  }

  function goBack() {
    const steps = stepsFor(draft.regionId, draft);
    const index = steps.indexOf(step);
    if (index > 0) {
      setStep(steps[index - 1]);
    }
  }

  function handleSeeActivities() {
    submit(draft);
  }

  function submit(filters: SearchFiltersState) {
    const submitted = withoutImpliedOpenLocation(filters);
    setFilters(submitted);
    saveRecentSearch(submitted);
    closeNavigator();
    router.push(buildSearchPageHref(locale, submitted));
  }

  const areasSelectable = isAllAreasSelectable();
  const regionsOpen = openRegions();
  const neighbourhoodChoices = allowedNeighbourhoodsForRegion(draft.regionId);
  const onlyNeighbourhood =
    neighbourhoodChoices.length === 1 ? neighbourhoodChoices[0] : undefined;

  const forwardAction =
    step === 'location' && regionsOpen.length === 0 ? (
      <Button
        type="button"
        className="min-w-0 flex-1"
        onClick={() => selectLocation(null)}
      >
        {copy.continueLabel}
      </Button>
    ) : step === 'neighbourhood' && onlyNeighbourhood ? (
      <Button
        type="button"
        className="min-w-0 flex-1"
        onClick={() => selectNeighbourhood(onlyNeighbourhood.id)}
      >
        {copy.continueLabel}
      </Button>
    ) : step === 'activity' ? (
      <Button
        type="button"
        className="min-w-0 flex-1"
        onClick={handleSeeActivities}
      >
        {copy.seeActivitiesLabel}
      </Button>
    ) : null;
  const backAction =
    step !== 'location' ? (
      <Button
        type="button"
        variant="secondary"
        className={forwardAction ? 'shrink-0' : 'w-full sm:w-auto'}
        onClick={goBack}
      >
        {copy.backLabel}
      </Button>
    ) : null;

  return (
    <>
      <button
        type="button"
        className={
          'mx-auto mt-8 flex min-h-14 w-full max-w-lg items-center ' +
          'justify-center rounded-full bg-accent-500 px-6 py-3.5 ' +
          'text-base font-bold text-ink-900 shadow-[0_12px_32px_rgba(46,29,18,0.22)] ' +
          'ring-2 ring-inset ring-ink-900/20 transition hover:bg-accent-600 ' +
          'sm:text-lg'
        }
        onClick={openNavigator}
      >
        {copy.buttonLabel}
      </button>
      <Modal
        isOpen={isOpen}
        title={copy.steps[step].title}
        onClose={closeNavigator}
        footer={
          backAction || forwardAction ? (
            <div className="flex items-center gap-3">
              {backAction}
              {forwardAction}
            </div>
          ) : undefined
        }
      >
        <p className="mb-3 text-sm text-ink-500 sm:mb-4">
          {formatContentTemplate(copy.stepProgressTemplate, {
            current: stepIndex(step, hasSelectedLocation ? draft.regionId : null, draft),
            total: stepsFor(hasSelectedLocation ? draft.regionId : null, draft).length,
          })}
        </p>
        {step === 'location' ? (
          <fieldset>
            <legend className="sr-only">{copy.steps.location.label}</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-4">
              <ChoiceTile
                label={
                  getConfiguredSearchAreaScope().restricted
                    ? copy.allAreasLabel
                    : copy.allHongKongLabel
                }
                iconSrc={ALL_HONG_KONG_ICON_SRC}
                iconShape="flag"
                isSelected={
                  areasSelectable &&
                  hasSelectedLocation &&
                  draft.regionId === null
                }
                disabled={!areasSelectable}
                disabledHint={
                  areasSelectable
                    ? undefined
                    : regionsOpen.length === 0
                      ? copy.noAreasOpenLabel
                      : formatContentTemplate(copy.onlyRegionOpenTemplate, {
                          region: regionLabel(
                            regionsOpen[0]?.id ?? null,
                            locale,
                          ),
                        })
                }
                onClick={() => selectLocation(null)}
              />
              {REGION_ROW_ORDER.map((regionId) => {
                const region = REGIONS_BY_ID.get(regionId);
                const iconSrc = iconSrcForRegion(regionId);
                if (!region || !iconSrc) {
                  return null;
                }
                const selectable = isRegionSelectable(region.id);
                return (
                  <ChoiceTile
                    key={region.id}
                    label={labelForLocale(region.labels, locale)}
                    iconSrc={iconSrc}
                    isSelected={selectable && draft.regionId === region.id}
                    disabled={!selectable}
                    disabledHint={
                      selectable ? undefined : copy.regionUnavailableLabel
                    }
                    onClick={() => selectLocation(region.id)}
                  />
                );
              })}
            </div>
          </fieldset>
        ) : null}
        {step === 'neighbourhood' ? (
          <fieldset>
            <legend className="sr-only">
              {copy.steps.neighbourhood.label}
            </legend>
            <div className="flex flex-wrap gap-2 sm:max-h-80 sm:overflow-y-auto">
              {neighbourhoodChoices.length > 1 ? (
                <button
                  type="button"
                  className={neighbourhoodButtonClass(
                    draft.neighbourhoodId == null,
                  )}
                  aria-pressed={draft.neighbourhoodId == null}
                  onClick={() => selectNeighbourhood(null)}
                >
                  {formatContentTemplate(
                    getConfiguredSearchAreaScope().restricted
                      ? copy.allOpenAreasInRegionTemplate
                      : copy.anywhereInRegionTemplate,
                    { region: regionLabel(draft.regionId, locale) },
                  )}
                </button>
              ) : null}
              {neighbourhoodChoices.map((neighbourhood) => (
                <button
                  key={neighbourhood.id}
                  type="button"
                  className={neighbourhoodButtonClass(
                    draft.neighbourhoodId === neighbourhood.id,
                  )}
                  aria-pressed={draft.neighbourhoodId === neighbourhood.id}
                  onClick={() => selectNeighbourhood(neighbourhood.id)}
                >
                  {labelForLocale(neighbourhood.labels, locale)}
                </button>
              ))}
            </div>
          </fieldset>
        ) : null}
        {step === 'location' && regionsOpen.length === 0 ? (
          <p role="status" className="mt-3 text-sm text-ink-700">
            {copy.noAreasOpenLabel}
          </p>
        ) : null}
        {step === 'kind' ? (
          <fieldset>
            <legend className="sr-only">{copy.steps.kind.label}</legend>
            <div className="grid grid-cols-2 gap-2 sm:gap-4">
              {offeredKinds.map((kind) => (
                <ChoiceTile
                  key={kind.id}
                  label={labelForLocale(kind.labels, locale)}
                  hint={labelForLocale(kind.hint, locale)}
                  iconSrc={iconSrcForKind(kind.id)}
                  isSelected={draft.kind === kind.id}
                  size="compact"
                  onClick={() => selectKind(kind.id)}
                />
              ))}
              <ChoiceTile
                label={copy.weekendLabel}
                hint={copy.weekendHint}
                iconSrc={WEEKEND_ICON_SRC}
                isSelected={isWeekendPreset(draft)}
                size="compact"
                onClick={selectWeekend}
              />
            </div>
          </fieldset>
        ) : null}
        {step === 'age' ? (
          <fieldset>
            <legend className="sr-only">{copy.steps.age.label}</legend>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 sm:gap-4">
              {homeWizardChoices.ageGroups.map((group) => {
                const iconSrc = iconSrcForAge(group.id);
                if (!iconSrc) {
                  return null;
                }
                return (
                  <ChoiceTile
                    key={group.id}
                    label={labelForLocale(group.labels, locale)}
                    iconSrc={iconSrc}
                    isSelected={draft.ageGroupId === group.id}
                    size="compact"
                    onClick={() => selectAge(group.id)}
                  />
                );
              })}
            </div>
          </fieldset>
        ) : null}
        {step === 'activity' ? (
          <fieldset>
            <legend className="sr-only">{copy.steps.activity.label}</legend>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-4">
              {topicsToShow(offeredTopicIds, draft.activityTypeIds).map((type) => (
                <ChoiceTile
                  key={type.id}
                  label={labelForLocale(type.labels, locale)}
                  iconSrc={iconSrcForActivity(type.id)}
                  isSelected={draft.activityTypeIds.includes(type.id)}
                  onClick={() => toggleType(type.id)}
                />
              ))}
            </div>
          </fieldset>
        ) : null}
      </Modal>
    </>
  );
}
