import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SearchNavigator } from '@/components/sections/hero/search-navigator';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import {
  AGE_ICON_SRC,
  ALL_HONG_KONG_ICON_SRC,
  REGION_ICON_SRC,
  WEEKEND_ICON_SRC,
  iconSrcForActivity,
} from '@/lib/home-wizard/choice-icons';
import { homeWizardChoices } from '@/lib/home-wizard/choices';
import { clearSearchAreaScopeCacheForTests } from '@/lib/home-wizard/area-scope';

const push = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push,
  }),
}));

function renderNavigator() {
  const content = getContent('en');
  render(
    <SearchProvider>
      <main id="main-content">
        <SearchNavigator locale="en" copy={content.smallWorld.navigator} />
      </main>
    </SearchProvider>,
  );
  return content;
}

function openNavigator() {
  const content = renderNavigator();
  fireEvent.click(
    screen.getByRole('button', {
      name: content.smallWorld.navigator.buttonLabel,
    }),
  );
  return content;
}

function choiceImage(name: string): HTMLImageElement {
  const button = screen.getByRole('button', { name });
  const image = button.querySelector('img');
  expect(image).not.toBeNull();
  return image as HTMLImageElement;
}

describe('SearchNavigator', () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE;
    clearSearchAreaScopeCacheForTests();
    push.mockClear();
  });

  it('opens on the location step with large area tiles', () => {
    const content = openNavigator();

    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.location.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument();
    expect(choiceImage('All Hong Kong')).toHaveAttribute(
      'src',
      ALL_HONG_KONG_ICON_SRC,
    );
    expect(choiceImage('All Hong Kong')).toHaveClass(
      'choice-tile__icon',
      'h-14',
      'sm:h-24',
    );
    expect(choiceImage('Kowloon')).toHaveAttribute(
      'src',
      REGION_ICON_SRC.kowloon,
    );
    expect(
      screen.queryByRole('button', { name: '3–5 years' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Kowloon' }).closest('[inert]'),
    ).toBeNull();
  });

  it('auto-advances through location, kind, and age, then submits filters', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.neighbourhood.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Anywhere in Kowloon' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.kind.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 3 of 5')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /^Somewhere to eat with kids/ }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^A class or club/ }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.age.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 4 of 5')).toBeInTheDocument();
    expect(choiceImage('3–5 years')).toHaveAttribute(
      'src',
      AGE_ICON_SRC['3-5'],
    );
    expect(choiceImage('3–5 years')).toHaveClass(
      'choice-tile__icon',
      'h-14',
      'sm:h-[4.8rem]',
    );
    expect(
      screen.getByRole('button', { name: '3–5 years' }).parentElement,
    ).toHaveClass('grid-cols-3', 'sm:grid-cols-5');

    fireEvent.click(screen.getByRole('button', { name: '3–5 years' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.activity.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 5 of 5')).toBeInTheDocument();

    const workshop = screen.getByRole('button', {
      name: 'Art and making',
    });
    expect(workshop).toHaveAttribute('aria-pressed', 'false');
    expect(workshop.querySelector('img')).toHaveAttribute(
      'src',
      iconSrcForActivity(homeWizardChoices.activityTypes[3].id),
    );

    fireEvent.click(workshop);
    expect(workshop).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.activity.title,
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', {
        name: content.smallWorld.navigator.seeActivitiesLabel,
      }),
    );
    expect(push).toHaveBeenCalledWith(
      '/en/search/?kind=class&age=3-5&region=kowloon&types=art&view=map',
    );
  });

  it('pins Back and See activities under the choices in one row', () => {
    const content = openNavigator();
    const navigator = content.smallWorld.navigator;

    // The first step advances on a tap, so it has no bar to pin.
    expect(document.querySelector('[data-modal-footer]')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    fireEvent.click(screen.getByRole('button', { name: 'Anywhere in Kowloon' }));
    fireEvent.click(screen.getByRole('button', { name: /^A class or club/ }));
    const backOnAge = screen.getByRole('button', { name: navigator.backLabel });
    expect(backOnAge.closest('[data-modal-footer]')).not.toBeNull();
    expect(backOnAge).toHaveClass('w-full');

    fireEvent.click(screen.getByRole('button', { name: '3–5 years' }));
    const back = screen.getByRole('button', { name: navigator.backLabel });
    const see = screen.getByRole('button', { name: navigator.seeActivitiesLabel });
    for (const action of [back, see]) {
      expect(action.closest('[data-modal-footer]')).not.toBeNull();
      expect(action.closest('[data-modal-body]')).toBeNull();
    }
    expect(back.parentElement).toBe(see.parentElement);
    expect(back.parentElement).toHaveClass('flex', 'items-center');
    expect(back).toHaveClass('shrink-0');
    expect(see).toHaveClass('flex-1');
  });

  it('lets the sheet scroll the neighbourhoods on phones instead of a box inside it', () => {
    openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    const choice = screen.getByRole('button', { name: 'Mong Kok' });
    expect(choice).toHaveClass('min-h-11');
    expect(choice.parentElement).toHaveClass('sm:max-h-80', 'sm:overflow-y-auto');
    expect(choice.parentElement).not.toHaveClass('max-h-80', 'overflow-y-auto');
  });

  it('puts the chosen neighbourhood on the search URL', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mong Kok' }));
    fireEvent.click(screen.getByRole('button', { name: /^A camp or workshop/ }));
    fireEvent.click(screen.getByRole('button', { name: '3–5 years' }));
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Art and making',
      }),
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: content.smallWorld.navigator.seeActivitiesLabel,
      }),
    );

    expect(push).toHaveBeenCalledWith(
      '/en/search/?kind=camp&age=3-5&region=kowloon&neighbourhood=yau-tsim-mong-mong-kok&types=art&view=map',
    );
  });

  it('returns to the previous step without losing the selection', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Islands' }));
    fireEvent.click(
      screen.getByRole('button', { name: content.smallWorld.navigator.backLabel }),
    );

    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.location.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Islands' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('resets to the location step after close', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    fireEvent.click(
      screen.getByRole('button', {
        name: content.smallWorld.navigator.buttonLabel,
      }),
    );

    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.location.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '3–5 years' }),
    ).not.toBeInTheDocument();
  });

  it('greys out closed regions and shows the one open neighbourhood', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE =
      'central-and-western-kennedy-town';
    clearSearchAreaScopeCacheForTests();
    const content = openNavigator();

    const allAreas = screen.getByRole('button', { name: /All areas/ });
    expect(allAreas).toHaveAttribute('aria-disabled', 'true');
    expect(allAreas).not.toBeDisabled();
    expect(allAreas).toHaveTextContent('Only Hong Kong Island is open');
    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument();
    const kowloon = screen.getByRole('button', { name: /Kowloon/ });
    expect(kowloon).toHaveAttribute('aria-disabled', 'true');
    expect(kowloon).toHaveTextContent('Coming soon');
    fireEvent.click(kowloon);
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.location.title,
      }),
    ).toBeInTheDocument();

    const island = screen.getByRole('button', { name: 'Hong Kong Island' });
    expect(island).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(island);
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.neighbourhood.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Kennedy Town' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(
      screen.queryByRole('button', { name: /Anywhere/ }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.kind.title,
      }),
    ).toBeInTheDocument();
  });

  it('keeps every area available when more than one region is open', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'kowloon,islands';
    clearSearchAreaScopeCacheForTests();
    openNavigator();

    expect(screen.getByRole('button', { name: 'All areas' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Kowloon' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument();
  });

  it('can continue when the scope names no neighbourhood', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'atlantis';
    clearSearchAreaScopeCacheForTests();
    const content = openNavigator();

    expect(screen.getByRole('status')).toHaveTextContent(
      'No areas are open yet',
    );
    expect(screen.getByRole('button', { name: /All areas/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.kind.title,
      }),
    ).toBeInTheDocument();
  });

  it('does not write the starting choice into the search', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Hong Kong Island' }));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: /^A class or club/ }));
    fireEvent.click(screen.getByRole('button', { name: '3–5 years' }));
    fireEvent.click(
      screen.getByRole('button', { name: content.smallWorld.navigator.seeActivitiesLabel }),
    );
    expect(push).toHaveBeenCalledWith('/en/search/?kind=class&age=3-5&view=map');
  });

  it('submits on the age for a kind without topics', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'All Hong Kong' }));
    fireEvent.click(
      screen.getByRole('button', { name: /^Somewhere to go today/ }),
    );
    expect(screen.getByText('Step 3 of 3')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.age.title,
      }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Under 1' }));

    expect(push).toHaveBeenCalledWith(
      '/en/search/?kind=place&age=0-1&view=map',
    );
  });

  it('searches the weekend across every kind', () => {
    const content = openNavigator();
    const navigator = content.smallWorld.navigator;

    fireEvent.click(screen.getByRole('button', { name: 'All Hong Kong' }));
    const weekend = screen.getByRole('button', {
      name: (name) => name.startsWith(navigator.weekendLabel),
    });
    expect(weekend.querySelector('img')).toHaveAttribute('src', WEEKEND_ICON_SRC);
    fireEvent.click(weekend);
    fireEvent.click(screen.getByRole('button', { name: '6–11 years' }));

    expect(push).toHaveBeenCalledWith(
      '/en/search/?age=6-11&day=weekend&view=map',
    );
  });
});
