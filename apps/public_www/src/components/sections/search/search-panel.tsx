'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';

import type { Locale } from '@/content';
import { Button } from '@/components/shared/ui/button';
import { Modal } from '@/components/shared/ui/modal';
import { useSearchContext } from '@/components/shared/search/search-context';
import { saveRecentSearch } from '@/lib/activities/recent-storage';
import {
  buildSearchQueryString,
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

import { SearchChoiceButton } from './search-choice-button';

interface SearchPanelCopy {
  readonly title: string;
  readonly whereLabel: string;
  readonly neighbourhoodLabel: string;
  readonly anywhereInRegionLabel: string;
  readonly childAgeLabel: string;
  readonly activityTypesLabel: string;
  readonly searchLabel: string;
}

interface SearchPanelProps {
  readonly locale: Locale;
  readonly copy: SearchPanelCopy;
}

function allHongKongLabel(locale: Locale): string {
  return locale === 'zh-HK' ? '全港' : 'All Hong Kong';
}

export function SearchPanel({ locale, copy }: SearchPanelProps) {
  const router = useRouter();
  const { filters, isSearchOpen, setFilters, closeSearch } = useSearchContext();
  const [draft, setDraft] = useState<SearchFiltersState>(filters);

  useEffect(() => {
    if (isSearchOpen) {
      setDraft(filters);
    }
  }, [filters, isSearchOpen]);

  function updateDraft(partial: Partial<SearchFiltersState>) {
    setDraft((current) => ({ ...current, ...partial }));
  }

  function toggleType(typeId: string) {
    setDraft((current) => {
      const next = new Set(current.activityTypeIds);
      if (next.has(typeId)) {
        next.delete(typeId);
      } else {
        next.add(typeId);
      }
      return {
        ...current,
        activityTypeIds: [...next],
      };
    });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFilters(draft);
    saveRecentSearch(draft);
    closeSearch();
    const query = buildSearchQueryString(draft);
    const path = localizePath('/search', locale);
    router.push(query ? `${path}?${query}` : path);
  }

  const regionsById = new Map(
    homeWizardChoices.regions.map((region) => [region.id, region]),
  );

  return (
    <Modal isOpen={isSearchOpen} title={copy.title} onClose={closeSearch}>
      <form className="space-y-6" onSubmit={handleSubmit}>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-ink-900">
            {copy.whereLabel}
          </legend>
          <div className="flex flex-nowrap items-stretch gap-2 overflow-x-auto md:grid md:grid-cols-5 md:gap-3 md:overflow-visible">
            <SearchChoiceButton
              label={allHongKongLabel(locale)}
              iconSrc={ALL_HONG_KONG_ICON_SRC}
              iconShape="flag"
              isSelected={draft.regionId === null}
              onClick={() =>
                updateDraft({ regionId: null, neighbourhoodId: null })
              }
            />
            {REGION_ROW_ORDER.map((regionId) => {
              const region = regionsById.get(regionId);
              if (!region) {
                return null;
              }
              const iconSrc = iconSrcForRegion(region.id);
              if (!iconSrc) {
                return null;
              }
              return (
                <SearchChoiceButton
                  key={region.id}
                  label={labelForLocale(region.labels, locale)}
                  iconSrc={iconSrc}
                  isSelected={draft.regionId === region.id}
                  onClick={() =>
                    updateDraft({
                      regionId: region.id,
                      neighbourhoodId:
                        draft.regionId === region.id
                          ? draft.neighbourhoodId
                          : null,
                    })
                  }
                />
              );
            })}
          </div>
          {draft.regionId ? (
            <label className="mt-3 block text-sm font-semibold text-ink-900">
              {copy.neighbourhoodLabel}
              <select
                className="mt-2 w-full rounded-xl border border-brand-100 bg-white px-3 py-2 text-sm font-medium text-ink-900"
                value={draft.neighbourhoodId ?? ''}
                onChange={(event) =>
                  updateDraft({
                    neighbourhoodId: event.target.value || null,
                  })
                }
              >
                <option value="">{copy.anywhereInRegionLabel}</option>
                {neighbourhoodsForRegion(draft.regionId).map((neighbourhood) => (
                  <option key={neighbourhood.id} value={neighbourhood.id}>
                    {labelForLocale(neighbourhood.labels, locale)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </fieldset>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-ink-900">
            {copy.childAgeLabel}
          </legend>
          <div className="flex flex-wrap gap-2 md:gap-3">
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
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-ink-900">
            {copy.activityTypesLabel}
          </legend>
          <div className="flex flex-wrap gap-2 md:gap-3">
            {homeWizardChoices.activityTypes.map((type) => (
              <SearchChoiceButton
                key={type.id}
                label={labelForLocale(type.labels, locale)}
                iconSrc={iconSrcForActivity(type.id)}
                isSelected={draft.activityTypeIds.includes(type.id)}
                onClick={() => toggleType(type.id)}
              />
            ))}
          </div>
        </fieldset>
        <Button type="submit" className="w-full">
          {copy.searchLabel}
        </Button>
      </form>
    </Modal>
  );
}
