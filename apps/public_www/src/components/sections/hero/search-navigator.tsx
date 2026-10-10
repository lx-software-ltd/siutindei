'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';

import type { Locale, SiteContent } from '@/content';
import { Button } from '@/components/shared/ui/button';
import { ChoiceTile } from '@/components/shared/ui/choice-tile';
import { Modal } from '@/components/shared/ui/modal';
import { useSearchContext } from '@/components/shared/search/search-context';
import { formatContentTemplate } from '@/content/content-field-utils';
import { saveRecentSearch } from '@/lib/activities/recent-storage';
import {
  buildSearchQueryString,
  toggleActivityTypeId,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import {
  homeWizardChoices,
  labelForLocale,
  neighbourhoodsForRegion,
} from '@/lib/home-wizard/choices';
import {
  ALL_HONG_KONG_ICON_SRC,
  REGION_ROW_ORDER,
  iconSrcForActivity,
  iconSrcForAge,
  iconSrcForRegion,
} from '@/lib/home-wizard/choice-icons';
import { localizePath } from '@/lib/locale-routing';

function regionLabel(regionId: string | null, locale: Locale): string {
  const region = homeWizardChoices.regions.find((entry) => entry.id === regionId);
  return region ? labelForLocale(region.labels, locale) : '';
}

function neighbourhoodButtonClass(isSelected: boolean): string {
  const selected = isSelected
    ? 'border-accent-500 bg-brand-50'
    : 'border-brand-100 bg-white hover:border-brand-200';
  return (
    'rounded-full border px-4 py-2 text-sm font-semibold text-ink-900 ' +
    selected
  );
}

type NavigatorStep = 'location' | 'neighbourhood' | 'age' | 'activity';

function stepsFor(regionId: string | null): readonly NavigatorStep[] {
  if (regionId) {
    return ['location', 'neighbourhood', 'age', 'activity'];
  }
  return ['location', 'age', 'activity'];
}

const EMPTY_NAVIGATOR_FILTERS: SearchFiltersState = {
  ageGroupId: null,
  regionId: null,
  activityTypeIds: [],
  textQuery: '',
};

interface SearchNavigatorProps {
  readonly locale: Locale;
  readonly copy: SiteContent['smallWorld']['navigator'];
}

function stepIndex(step: NavigatorStep, regionId: string | null): number {
  return stepsFor(regionId).indexOf(step) + 1;
}

export function SearchNavigator({ locale, copy }: SearchNavigatorProps) {
  const router = useRouter();
  const { setFilters } = useSearchContext();
  const [isOpen, setIsOpen] = useState(false);
  const [step, setStep] = useState<NavigatorStep>('location');
  const [hasSelectedLocation, setHasSelectedLocation] = useState(false);
  const [draft, setDraft] = useState<SearchFiltersState>(
    EMPTY_NAVIGATOR_FILTERS,
  );

  const resetNavigator = useCallback(() => {
    setStep('location');
    setHasSelectedLocation(false);
    setDraft(EMPTY_NAVIGATOR_FILTERS);
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
    setDraft((current) => ({
      ...current,
      regionId,
      neighbourhoodId: null,
    }));
    setHasSelectedLocation(true);
    setStep(regionId ? 'neighbourhood' : 'age');
  }

  function selectNeighbourhood(neighbourhoodId: string | null) {
    setDraft((current) => ({ ...current, neighbourhoodId }));
    setStep('age');
  }

  function selectAge(ageGroupId: string) {
    setDraft((current) => ({ ...current, ageGroupId }));
    setStep('activity');
  }

  function toggleType(typeId: string) {
    setDraft((current) => toggleActivityTypeId(current, typeId));
  }

  function goBack() {
    const steps = stepsFor(draft.regionId);
    const index = steps.indexOf(step);
    if (index > 0) {
      setStep(steps[index - 1]);
    }
  }

  function handleSeeActivities() {
    setFilters(draft);
    saveRecentSearch(draft);
    const query = buildSearchQueryString(draft);
    const path = localizePath('/search', locale);
    closeNavigator();
    router.push(query ? `${path}?${query}` : path);
  }

  const regionsById = new Map(
    homeWizardChoices.regions.map((region) => [region.id, region]),
  );

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
      >
        <p className="mb-4 text-sm text-ink-500">
          {formatContentTemplate(copy.stepProgressTemplate, {
            current: stepIndex(step, hasSelectedLocation ? draft.regionId : null),
            total: stepsFor(hasSelectedLocation ? draft.regionId : null).length,
          })}
        </p>
        {step === 'location' ? (
          <fieldset>
            <legend className="sr-only">{copy.steps.location.label}</legend>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4">
              <ChoiceTile
                label={copy.allHongKongLabel}
                iconSrc={ALL_HONG_KONG_ICON_SRC}
                iconShape="flag"
                isSelected={hasSelectedLocation && draft.regionId === null}
                onClick={() => selectLocation(null)}
              />
              {REGION_ROW_ORDER.map((regionId) => {
                const region = regionsById.get(regionId);
                const iconSrc = iconSrcForRegion(regionId);
                if (!region || !iconSrc) {
                  return null;
                }
                return (
                  <ChoiceTile
                    key={region.id}
                    label={labelForLocale(region.labels, locale)}
                    iconSrc={iconSrc}
                    isSelected={draft.regionId === region.id}
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
            <div className="flex max-h-80 flex-wrap gap-2 overflow-y-auto">
              <button
                type="button"
                className={neighbourhoodButtonClass(draft.neighbourhoodId == null)}
                aria-pressed={draft.neighbourhoodId == null}
                onClick={() => selectNeighbourhood(null)}
              >
                {formatContentTemplate(copy.anywhereInRegionTemplate, {
                  region: regionLabel(draft.regionId, locale),
                })}
              </button>
              {neighbourhoodsForRegion(draft.regionId).map((neighbourhood) => (
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
        {step === 'age' ? (
          <fieldset>
            <legend className="sr-only">{copy.steps.age.label}</legend>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
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
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
              {homeWizardChoices.activityTypes.map((type) => (
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
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          {step !== 'location' ? (
            <Button
              type="button"
              variant="secondary"
              className="sm:w-auto"
              onClick={goBack}
            >
              {copy.backLabel}
            </Button>
          ) : null}
          {step === 'activity' ? (
            <Button
              type="button"
              className="w-full sm:flex-1"
              onClick={handleSeeActivities}
            >
              {copy.seeActivitiesLabel}
            </Button>
          ) : null}
        </div>
      </Modal>
    </>
  );
}
