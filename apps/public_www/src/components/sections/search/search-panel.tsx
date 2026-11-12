'use client';

import { useEffect, useId, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';

import type { Locale } from '@/content/locales';
import { formatContentTemplate } from '@/content/content-field-utils';
import { Button } from '@/components/shared/ui/button';
import { Modal } from '@/components/shared/ui/modal';
import { useSearchContext } from '@/components/shared/search/search-context';
import { saveRecentSearch } from '@/lib/activities/recent-storage';
import {
  toggleActivityTypeId,
  type SearchFiltersState,
} from '@/lib/activities/search-params';
import { buildSearchPageHref } from '@/lib/activities/map-search-url';
import {
  allowedNeighbourhoodsForRegion,
  getConfiguredSearchAreaScope,
  isAllAreasSelectable,
  isRegionSelectable,
  openRegions,
  sanitizeSearchFilters,
  showsNeighbourhoodChoices,
  withDefaultOpenLocation,
  withoutImpliedOpenLocation,
} from '@/lib/home-wizard/area-scope';
import { REGIONS_BY_ID } from '@/lib/home-wizard/choices';
import {
  homeWizardChoices,
  labelForLocale,
} from '@/lib/home-wizard/choices';
import {
  ALL_HONG_KONG_ICON_SRC,
  REGION_ROW_ORDER,
  iconSrcForActivity,
  iconSrcForAge,
  iconSrcForRegion,
} from '@/lib/home-wizard/choice-icons';
import { ChoiceCarousel } from './choice-carousel';
import { SearchChoiceButton } from './search-choice-button';

interface SearchPanelCopy {
  readonly title: string;
  readonly whereLabel: string;
  readonly neighbourhoodLabel: string;
  readonly anywhereInRegionLabel: string;
  readonly childAgeLabel: string;
  readonly activityTypesLabel: string;
  readonly activityTypesPreviousLabel: string;
  readonly activityTypesNextLabel: string;
  readonly searchLabel: string;
  readonly allHongKongLabel: string;
  readonly allAreasLabel: string;
  readonly regionUnavailableLabel: string;
  readonly onlyRegionOpenTemplate: string;
  readonly allOpenAreasInRegionTemplate: string;
  readonly noAreasOpenLabel: string;
}

function NeighbourhoodSelect({
  locale,
  regionId,
  neighbourhoodId,
  restricted,
  anywhereLabel,
  allOpenAreasTemplate,
  legend,
  onChange,
}: {
  readonly locale: Locale;
  readonly regionId: string;
  readonly neighbourhoodId: string | null;
  readonly restricted: boolean;
  readonly anywhereLabel: string;
  readonly allOpenAreasTemplate: string;
  readonly legend: string;
  readonly onChange: (neighbourhoodId: string | null) => void;
}) {
  const allowed = allowedNeighbourhoodsForRegion(regionId);
  const region = REGIONS_BY_ID.get(regionId);
  const anywhere = restricted
    ? formatContentTemplate(allOpenAreasTemplate, {
        region: region ? labelForLocale(region.labels, locale) : '',
      })
    : anywhereLabel;
  // The longest option is a select's minimum width, which stretches the
  // sheet past the phone. The column locks the control to the sheet.
  return (
    <label className="mt-3 grid w-full min-w-0 grid-cols-[minmax(0,1fr)] text-sm font-semibold text-ink-900">
      {legend}
      <select
        className="mt-2 w-full min-w-0 max-w-full rounded-xl border border-brand-100 bg-white px-3 py-2 text-sm font-medium text-ink-900 [field-sizing:fixed]"
        value={neighbourhoodId ?? ''}
        onChange={(event) => onChange(event.target.value || null)}
      >
        {allowed.length > 1 ? <option value="">{anywhere}</option> : null}
        {allowed.map((neighbourhood) => (
          <option key={neighbourhood.id} value={neighbourhood.id}>
            {labelForLocale(neighbourhood.labels, locale)}
          </option>
        ))}
      </select>
    </label>
  );
}

interface SearchPanelProps {
  readonly locale: Locale;
  readonly copy: SearchPanelCopy;
}

export function SearchPanel({ locale, copy }: SearchPanelProps) {
  const router = useRouter();
  const formId = useId();
  const { filters, isSearchOpen, setFilters, closeSearch } = useSearchContext();
  const [draft, setDraft] = useState<SearchFiltersState>(() =>
    withDefaultOpenLocation(sanitizeSearchFilters(filters).filters),
  );
  const scope = getConfiguredSearchAreaScope();
  const areaLabel = scope.restricted
    ? copy.allAreasLabel
    : copy.allHongKongLabel;
  const allAreasSelectable = isAllAreasSelectable();
  const regions = openRegions();
  const onlyRegion =
    regions.length === 1 ? REGIONS_BY_ID.get(regions[0].id) : undefined;
  const allAreasHint = allAreasSelectable
    ? undefined
    : regions.length === 0
      ? copy.noAreasOpenLabel
      : formatContentTemplate(copy.onlyRegionOpenTemplate, {
          region: onlyRegion ? labelForLocale(onlyRegion.labels, locale) : '',
        });

  useEffect(() => {
    if (isSearchOpen) {
      setDraft(withDefaultOpenLocation(sanitizeSearchFilters(filters).filters));
    }
  }, [filters, isSearchOpen]);

  function updateDraft(partial: Partial<SearchFiltersState>) {
    setDraft((current) => ({ ...current, ...partial }));
  }

  function toggleType(typeId: string) {
    setDraft((current) => toggleActivityTypeId(current, typeId));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const submitted = withoutImpliedOpenLocation(draft);
    setFilters(submitted);
    saveRecentSearch(submitted);
    closeSearch();
    router.push(buildSearchPageHref(locale, submitted));
  }

  return (
    <Modal
      isOpen={isSearchOpen}
      title={copy.title}
      onClose={closeSearch}
      footer={
        <Button type="submit" form={formId} className="w-full">
          {copy.searchLabel}
        </Button>
      }
    >
      <form id={formId} className="w-full min-w-0 space-y-6" onSubmit={handleSubmit}>
        <fieldset className="min-w-0">
          <legend className="mb-2 text-sm font-semibold text-ink-900">
            {copy.whereLabel}
          </legend>
          <div className="flex w-full min-w-0 max-w-full flex-wrap items-stretch gap-2 md:grid md:grid-cols-5 md:gap-3">
            <SearchChoiceButton
              label={areaLabel}
              iconSrc={ALL_HONG_KONG_ICON_SRC}
              iconShape="flag"
              isSelected={allAreasSelectable && draft.regionId === null}
              disabled={!allAreasSelectable}
              disabledHint={allAreasHint}
              onClick={() =>
                updateDraft({ regionId: null, neighbourhoodId: null })
              }
            />
            {REGION_ROW_ORDER.map((regionId) => {
              const region = REGIONS_BY_ID.get(regionId);
              if (!region) {
                return null;
              }
              const iconSrc = iconSrcForRegion(region.id);
              if (!iconSrc) {
                return null;
              }
              const selectable = isRegionSelectable(region.id);
              return (
                <SearchChoiceButton
                  key={region.id}
                  label={labelForLocale(region.labels, locale)}
                  iconSrc={iconSrc}
                  isSelected={selectable && draft.regionId === region.id}
                  disabled={!selectable}
                  disabledHint={
                    selectable ? undefined : copy.regionUnavailableLabel
                  }
                  onClick={() => {
                    const allowed = allowedNeighbourhoodsForRegion(region.id);
                    updateDraft({
                      regionId: region.id,
                      neighbourhoodId:
                        allowed.length === 1
                          ? allowed[0].id
                          : draft.regionId === region.id
                            ? draft.neighbourhoodId
                            : null,
                    });
                  }}
                />
              );
            })}
          </div>
          {draft.regionId && showsNeighbourhoodChoices(draft.regionId) ? (
            <NeighbourhoodSelect
              locale={locale}
              regionId={draft.regionId}
              neighbourhoodId={draft.neighbourhoodId}
              restricted={scope.restricted}
              anywhereLabel={copy.anywhereInRegionLabel}
              allOpenAreasTemplate={copy.allOpenAreasInRegionTemplate}
              legend={copy.neighbourhoodLabel}
              onChange={(neighbourhoodId) => updateDraft({ neighbourhoodId })}
            />
          ) : null}
          {regions.length === 0 ? (
            <p role="status" className="mt-3 text-sm text-ink-700">
              {copy.noAreasOpenLabel}
            </p>
          ) : null}
        </fieldset>
        <fieldset className="min-w-0">
          <legend className="mb-2 text-sm font-semibold text-ink-900">
            {copy.childAgeLabel}
          </legend>
          <div className="flex w-full min-w-0 max-w-full flex-wrap gap-2 md:gap-3">
            {homeWizardChoices.ageGroups.map((group) => {
              const iconSrc = iconSrcForAge(group.id);
              if (!iconSrc) {
                return null;
              }
              return (
                <SearchChoiceButton
                  key={group.id}
                  label={labelForLocale(group.labels, locale)}
                  iconSrc={iconSrc}
                  isSelected={draft.ageGroupId === group.id}
                  onClick={() => updateDraft({ ageGroupId: group.id })}
                />
              );
            })}
          </div>
        </fieldset>
        <fieldset className="min-w-0">
          <legend className="mb-2 text-sm font-semibold text-ink-900">
            {copy.activityTypesLabel}
          </legend>
          <ChoiceCarousel
            ariaLabel={copy.activityTypesLabel}
            previousLabel={copy.activityTypesPreviousLabel}
            nextLabel={copy.activityTypesNextLabel}
          >
            {homeWizardChoices.activityTypes.map((type) => (
              <SearchChoiceButton
                key={type.id}
                label={labelForLocale(type.labels, locale)}
                iconSrc={iconSrcForActivity(type.id)}
                isSelected={draft.activityTypeIds.includes(type.id)}
                layout="carousel"
                onClick={() => toggleType(type.id)}
              />
            ))}
          </ChoiceCarousel>
        </fieldset>
      </form>
    </Modal>
  );
}
