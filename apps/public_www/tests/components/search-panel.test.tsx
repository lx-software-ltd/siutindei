import { useEffect } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SearchPanel } from '@/components/sections/search/search-panel';
import {
  SearchProvider,
  useSearchContext,
} from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import {
  AGE_ICON_SRC,
  ALL_HONG_KONG_ICON_SRC,
  REGION_ICON_SRC,
} from '@/lib/home-wizard/choice-icons';
import { homeWizardChoices } from '@/lib/home-wizard/choices';

const push = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push,
  }),
}));

function OpenOnMount() {
  const { openSearch } = useSearchContext();
  useEffect(() => {
    openSearch();
  }, [openSearch]);
  return null;
}

function renderPanel() {
  const content = getContent('en');
  render(
    <SearchProvider>
      <OpenOnMount />
      <SearchPanel locale="en" copy={content.navbar.searchPanel} />
    </SearchProvider>,
  );
  return content;
}

function choiceImage(name: string): HTMLImageElement {
  const button = screen.getByRole('button', { name });
  const image = button.querySelector('img');
  expect(image).not.toBeNull();
  return image as HTMLImageElement;
}

describe('SearchPanel', () => {
  it('shows activity, age, and Hong Kong region icons with labels', () => {
    renderPanel();

    expect(choiceImage('All Hong Kong')).toHaveAttribute(
      'src',
      ALL_HONG_KONG_ICON_SRC,
    );

    expect(choiceImage('Hong Kong Island')).toHaveAttribute(
      'src',
      REGION_ICON_SRC.hong_kong_island,
    );
    expect(choiceImage('Kowloon')).toHaveAttribute(
      'src',
      REGION_ICON_SRC.kowloon,
    );
    expect(choiceImage('New Territories')).toHaveAttribute(
      'src',
      REGION_ICON_SRC.new_territories,
    );
    expect(choiceImage('Islands')).toHaveAttribute(
      'src',
      REGION_ICON_SRC.islands,
    );

    for (const group of homeWizardChoices.ageGroups) {
      expect(choiceImage(group.labels.en)).toHaveAttribute(
        'src',
        AGE_ICON_SRC[group.id],
      );
    }

    for (const type of homeWizardChoices.activityTypes) {
      expect(choiceImage(type.labels.en)).toHaveAttribute(
        'src',
        `/images/categories/${type.id}.svg`,
      );
    }
  });

  it('lists areas in one row from All Hong Kong to the islands', () => {
    renderPanel();

    const areaLabels = [
      'All Hong Kong',
      'Hong Kong Island',
      'Kowloon',
      'New Territories',
      'Islands',
    ];
    const choiceLabels = [...document.querySelectorAll('.search-choice')].map(
      (element) => element.textContent,
    );
    expect(choiceLabels.slice(0, areaLabels.length)).toEqual(areaLabels);

    const areaIconSlots = [...document.querySelectorAll('.search-choice')]
      .slice(0, areaLabels.length)
      .map((element) => element.querySelector('.search-choice-icon'));
    expect(areaIconSlots.every((slot) => slot !== null)).toBe(true);
    expect(
      areaIconSlots.every((slot) =>
        slot?.classList.contains('h-12'),
      ),
    ).toBe(true);
  });

  it('toggles an activity type when its choice is pressed', () => {
    renderPanel();

    const workshop = screen.getByRole('button', {
      name: 'Early years and schools',
    });
    expect(workshop).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(workshop);
    expect(workshop).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(workshop);
    expect(workshop).toHaveAttribute('aria-pressed', 'false');
  });

  it('does not show a clear activity types button', () => {
    renderPanel();

    fireEvent.click(
      screen.getByRole('button', { name: 'Early years and schools' }),
    );

    expect(
      screen.queryByRole('button', { name: 'Clear activity types' }),
    ).toBeNull();
  });
});
