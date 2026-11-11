import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FilterChipRow } from '@/components/sections/search/filter-chip-row';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import { iconSrcForActivity } from '@/lib/home-wizard/choice-icons';
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

  it('places each activity icon to the left of its label', () => {
    renderChipRow();

    for (const type of homeWizardChoices.activityTypes) {
      const chip = screen.getByRole('button', { name: type.labels.en });
      const icon = chip.querySelector('img');
      expect(icon).not.toBeNull();
      expect(icon).toHaveAttribute('src', iconSrcForActivity(type.id));
      expect(icon).toHaveAttribute('width', '20');
      expect(icon).toHaveAttribute('height', '20');
      expect(chip.firstElementChild).toBe(icon);
    }
  });

  it('toggles an activity type when its chip is pressed', () => {
    renderChipRow();

    const firstType = homeWizardChoices.activityTypes[0];
    const chip = screen.getByRole('button', { name: firstType.labels.en });

    expect(chip.className).not.toContain('bg-accent-500');

    fireEvent.click(chip);
    expect(chip.className).toContain('bg-accent-500');

    fireEvent.click(chip);
    expect(chip.className).not.toContain('bg-accent-500');
  });

  it('writes the selected type into the search URL', () => {
    renderChipRow();

    const workshop = homeWizardChoices.activityTypes[0];
    const classType = homeWizardChoices.activityTypes[1];
    fireEvent.click(screen.getByRole('button', { name: workshop.labels.en }));

    expect(replace).toHaveBeenCalledWith(
      `/en/search/?types=${workshop.id}&view=map`,
    );

    fireEvent.click(screen.getByRole('button', { name: classType.labels.en }));
    expect(replace).toHaveBeenLastCalledWith(
      `/en/search/?types=${workshop.id}%2C${classType.id}&view=map`,
    );

    fireEvent.click(screen.getByRole('button', { name: workshop.labels.en }));
    expect(replace).toHaveBeenLastCalledWith(
      `/en/search/?types=${classType.id}&view=map`,
    );

    fireEvent.click(screen.getByRole('button', { name: classType.labels.en }));
    expect(replace).toHaveBeenLastCalledWith(
      `/en/search/?view=map`,
    );
  });

  it('keeps list view in the query string when toggling a type', () => {
    currentSearchParams.value = new URLSearchParams('view=list');
    renderChipRow();

    const workshop = homeWizardChoices.activityTypes[0];
    fireEvent.click(screen.getByRole('button', { name: workshop.labels.en }));

    expect(replace).toHaveBeenCalledWith(
      `/en/search/?types=${workshop.id}&view=list`,
    );
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
