import { useEffect } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

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
import { clearSearchAreaScopeCacheForTests } from '@/lib/home-wizard/area-scope';
import { loadRecentSearch } from '@/lib/activities/recent-storage';

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
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
    window.localStorage.clear();
    push.mockClear();
  });

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

  it('lists areas in order from All Hong Kong to the islands', () => {
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

  it('wraps the area choices on phones so none run off the screen', () => {
    renderPanel();

    const row = screen.getByRole('button', {
      name: 'Hong Kong Island',
    }).parentElement;
    expect(row).toHaveClass('flex-wrap', 'min-w-0', 'max-w-full', 'md:grid', 'md:grid-cols-5');
    expect(row).not.toHaveClass('flex-nowrap');
    for (const fieldset of document.querySelectorAll('fieldset')) {
      expect(fieldset).toHaveClass('min-w-0');
    }
  });

  it('keeps Search in the pinned footer and still submits the form', () => {
    renderPanel();

    const search = screen.getByRole('button', { name: 'Search' });
    expect(search.closest('[data-modal-footer]')).not.toBeNull();
    expect(search.closest('[data-modal-body]')).toBeNull();

    fireEvent.click(search);
    expect(push).toHaveBeenCalledTimes(1);
  });

  it('pages activity types in a carousel of larger two-line cards', () => {
    renderPanel();

    const track = screen.getByRole('region', { name: 'Activity types' });
    expect(track).toHaveClass(
      'listing-carousel__track',
      'flex-wrap',
      'md:flex-nowrap',
      'md:overflow-x-auto',
    );
    expect(track).not.toHaveClass('overflow-x-scroll');

    const workshop = screen.getByRole('button', {
      name: 'Early years and schools',
    });
    expect(workshop).toHaveClass(
      'md:w-[calc((100%-1.5rem)/3)]',
      'md:snap-start',
    );
    expect(workshop).not.toHaveClass('md:flex-1');
    expect(workshop.querySelector('span:last-child')).toHaveClass(
      'md:line-clamp-2',
    );

    const previous = screen.getByRole('button', {
      name: 'Previous activity types',
    });
    const next = screen.getByRole('button', { name: 'Next activity types' });
    expect(previous).toBeDisabled();
    expect(next).toBeEnabled();

    Object.defineProperty(track, 'clientWidth', { configurable: true, value: 330 });
    Object.defineProperty(track, 'scrollWidth', { configurable: true, value: 770 });
    const card = track.firstElementChild;
    expect(card).not.toBeNull();
    Object.defineProperty(card, 'offsetWidth', { configurable: true, value: 100 });
    const scrollTo = vi.fn();
    track.scrollTo = scrollTo;

    fireEvent.click(next);
    expect(scrollTo).toHaveBeenCalledWith({ left: 300, behavior: 'smooth' });
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

  it('locks the neighbourhood menu to the sheet width', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'hong_kong_island';
    clearSearchAreaScopeCacheForTests();
    renderPanel();

    const neighbourhoods = screen.getByRole('combobox');
    expect(neighbourhoods).toHaveClass('min-w-0', 'max-w-full', 'w-full');
    expect(neighbourhoods.className).toContain('[field-sizing:fixed]');
    expect(neighbourhoods.parentElement).toHaveClass(
      'grid',
      'min-w-0',
      'w-full',
      'grid-cols-[minmax(0,1fr)]',
    );
    expect(
      neighbourhoods.querySelector('option')?.textContent,
    ).toBe('All open areas in Hong Kong Island');
  });

  it('hides neighbourhoods outside the scope', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'yau-tsim-mong';
    clearSearchAreaScopeCacheForTests();
    renderPanel();

    const allAreas = screen.getByRole('button', { name: /All areas/ });
    expect(allAreas).toHaveAttribute('aria-disabled', 'true');
    expect(allAreas).toHaveTextContent('Only Kowloon is open');
    expect(screen.getByRole('button', { name: 'Kowloon' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    const islands = screen.getByRole('button', { name: /Islands/ });
    expect(islands).toHaveAttribute('aria-disabled', 'true');
    expect(islands).not.toBeDisabled();

    const neighbourhoods = screen.getByRole('combobox');
    const labels = [...neighbourhoods.querySelectorAll('option')].map(
      (option) => option.textContent,
    );
    expect(labels[0]).toBe('All open areas in Kowloon');
    expect(labels).toContain('Mong Kok');
    expect(labels).not.toContain('Kennedy Town');

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'yau-tsim-mong-mong-kok' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    const href = String(push.mock.calls.at(-1)?.[0]);
    expect(href).toContain('region=kowloon');
    expect(href).toContain('neighbourhood=yau-tsim-mong-mong-kok');
  });

  it('shows the only open neighbourhood and greys out every area', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    renderPanel();

    const allAreas = screen.getByRole('button', { name: /All areas/ });
    expect(allAreas).toHaveAttribute('aria-disabled', 'true');
    expect(allAreas).not.toBeDisabled();
    expect(allAreas).toHaveTextContent('Only Hong Kong Island is open');
    expect(
      screen.getByRole('button', { name: 'Hong Kong Island' }),
    ).toHaveAttribute('aria-pressed', 'true');

    const labels = [
      ...screen.getByRole('combobox').querySelectorAll('option'),
    ].map((option) => option.textContent);
    expect(labels).toEqual(['Stanley']);

    fireEvent.click(allAreas);
    expect(
      screen.getByRole('button', { name: 'Hong Kong Island' }),
    ).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    expect(push).toHaveBeenCalledWith('/en/search/?view=map');
    expect(loadRecentSearch()?.regionId).toBeNull();
  });

  it('keeps every area available when more than one region is open', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,islands';
    clearSearchAreaScopeCacheForTests();
    renderPanel();

    expect(screen.getByRole('button', { name: 'All areas' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Kowloon' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('explains when the scope names no neighbourhood', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'atlantis';
    clearSearchAreaScopeCacheForTests();
    renderPanel();

    expect(screen.getByRole('status')).toHaveTextContent(
      'No areas are open yet',
    );
    expect(screen.getByRole('button', { name: /All areas/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    expect(screen.getByRole('button', { name: /Kowloon/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });

  it('names the only open neighbourhood in traditional chinese', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    const content = getContent('zh-HK');
    render(
      <SearchProvider>
        <OpenOnMount />
        <SearchPanel locale="zh-HK" copy={content.navbar.searchPanel} />
      </SearchProvider>,
    );

    expect(screen.getByRole('button', { name: /所有地區/ })).toHaveTextContent(
      '而家只開放香港島',
    );
    expect(screen.getByRole('combobox')).toHaveTextContent('赤柱');
  });
});
