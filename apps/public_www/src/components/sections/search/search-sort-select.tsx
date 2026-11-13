'use client';

import type { SiteContent } from '@/content/types';
import { ChipSelect } from '@/components/shared/ui/chip-select';
import type { SearchFiltersState } from '@/lib/activities/search-params';
import { formatTemplate } from '@/lib/format-template';

interface SearchSortSelectProps {
  readonly copy: SiteContent['searchPage'];
  readonly filters: SearchFiltersState;
  readonly onApply: (next: SearchFiltersState) => void;
  /** Among the filter chips a bare choice reads as a filter, so it names itself. */
  readonly namesItself?: boolean;
  readonly className?: string;
}

export function SearchSortSelect({
  copy,
  filters,
  onApply,
  namesItself = false,
  className = '',
}: SearchSortSelectProps) {
  const optionLabel = (choice: string) =>
    namesItself ? formatTemplate(copy.sortChoiceTemplate, { choice }) : choice;

  return (
    <ChipSelect
      className={className}
      label={copy.sortLabel}
      value={filters.sort === 'price' ? 'price' : 'time'}
      emptyValue="time"
      options={[
        { value: 'time', label: optionLabel(copy.sortTimeLabel) },
        { value: 'price', label: optionLabel(copy.sortPriceLabel) },
      ]}
      onValueChange={(value) =>
        onApply(
          value === 'price'
            ? { ...filters, sort: 'price' }
            : { ...filters, sort: undefined },
        )
      }
    />
  );
}
