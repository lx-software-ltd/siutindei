import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FilterChipRow } from '@/components/sections/search/filter-chip-row';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { homeWizardChoices } from '@/lib/home-wizard/choices';

const replace = vi.hoisted(() => vi.fn());
const currentSearchParams = vi.hoisted(() => ({
  value: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    replace,
  }),
  useSearchParams: () => currentSearchParams.value,
}));

const copy = getContent('en').searchPage;

function renderChipRow() {
  render(
    <SearchProvider>
      <FilterChipRow locale="en" copy={copy} />
    </SearchProvider>,
  );
}

describe('FilterChipRow', () => {
  beforeEach(() => {
    replace.mockClear();
    currentSearchParams.value = new URLSearchParams();
  });

  it('centers the refinement filters and leaves activity types off the bar', () => {
    renderChipRow();

    const group = screen.getByRole('group', { name: copy.filtersLabel });
    expect(group).toHaveClass('[justify-content:safe_center]');
    expect(group.querySelector('.w-px')).toBeNull();

    for (const type of homeWizardChoices.activityTypes) {
      expect(
        screen.queryByRole('button', { name: type.labels.en }),
      ).not.toBeInTheDocument();
    }
  });

  it('keeps list view in the query string when a filter changes', () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    renderChipRow();

    fireEvent.click(screen.getByRole('button', { name: copy.freeFilterLabel }));

    expect(replace).toHaveBeenCalledWith('/en/search/?free=1&view=list');
  });

  it('toggles the free and free trial refinements', () => {
    renderChipRow();

    const free = screen.getByRole('button', { name: copy.freeFilterLabel });
    expect(free).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(free);
    expect(replace).toHaveBeenLastCalledWith('/en/search/?free=1&view=map');
    expect(free).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: copy.freeTrialFilterLabel }));
    expect(replace).toHaveBeenLastCalledWith('/en/search/?free=1&trial=1&view=map');
  });

  it('writes day, language, and price choices into the search URL', () => {
    renderChipRow();

    fireEvent.change(screen.getByRole('combobox', { name: copy.dayFilterLabel }), {
      target: { value: 'weekend' },
    });
    expect(replace).toHaveBeenLastCalledWith('/en/search/?day=weekend&view=map');

    fireEvent.change(screen.getByRole('combobox', { name: copy.languageFilterLabel }), {
      target: { value: 'yue' },
    });
    expect(replace).toHaveBeenLastCalledWith('/en/search/?day=weekend&lang=yue&view=map');

    const price = screen.getByRole('combobox', { name: copy.priceFilterLabel });
    expect(screen.getByRole('option', { name: 'Up to HK$250 a class' })).toBeInTheDocument();
    fireEvent.change(price, { target: { value: '250' } });
    expect(replace).toHaveBeenLastCalledWith(
      '/en/search/?day=weekend&lang=yue&price=250&view=map',
    );

    fireEvent.change(price, { target: { value: '' } });
    expect(replace).toHaveBeenLastCalledWith('/en/search/?day=weekend&lang=yue&view=map');
  });
});
