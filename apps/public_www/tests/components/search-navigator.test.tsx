import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SearchNavigator } from '@/components/sections/hero/search-navigator';
import { SearchProvider } from '@/components/shared/search/search-context';
import { getContent } from '@/content';
import {
  AGE_ICON_SRC,
  ALL_HONG_KONG_ICON_SRC,
  REGION_ICON_SRC,
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
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
    expect(choiceImage('All Hong Kong')).toHaveAttribute(
      'src',
      ALL_HONG_KONG_ICON_SRC,
    );
    expect(choiceImage('All Hong Kong')).toHaveClass(
      'choice-tile__icon',
      'h-20',
    );
    expect(choiceImage('Kowloon')).toHaveAttribute(
      'src',
      REGION_ICON_SRC.kowloon,
    );
    expect(
      screen.queryByRole('button', { name: '3–6 years' }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Kowloon' }).closest('[inert]'),
    ).toBeNull();
  });

  it('auto-advances through location and age, then submits filters', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.neighbourhood.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 2 of 4')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Anywhere in Kowloon' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.age.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 3 of 4')).toBeInTheDocument();
    expect(choiceImage('3–6 years')).toHaveAttribute(
      'src',
      AGE_ICON_SRC['3-6'],
    );
    expect(choiceImage('3–6 years')).toHaveClass(
      'choice-tile__icon',
      'h-16',
    );

    fireEvent.click(screen.getByRole('button', { name: '3–6 years' }));
    expect(
      screen.getByRole('heading', {
        name: content.smallWorld.navigator.steps.activity.title,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Step 4 of 4')).toBeInTheDocument();

    const workshop = screen.getByRole('button', {
      name: 'Early years and schools',
    });
    expect(workshop).toHaveAttribute('aria-pressed', 'false');
    expect(workshop.querySelector('img')).toHaveAttribute(
      'src',
      `/images/categories/${homeWizardChoices.activityTypes[0].id}.svg`,
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
      '/en/search/?age=3-6&region=kowloon&types=early-years&view=map',
    );
  });

  it('puts the chosen neighbourhood on the search URL', () => {
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Kowloon' }));
    fireEvent.click(screen.getByRole('button', { name: 'Mong Kok' }));
    fireEvent.click(screen.getByRole('button', { name: '3–6 years' }));
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Early years and schools',
      }),
    );
    fireEvent.click(
      screen.getByRole('button', {
        name: content.smallWorld.navigator.seeActivitiesLabel,
      }),
    );

    expect(push).toHaveBeenCalledWith(
      '/en/search/?age=3-6&region=kowloon&neighbourhood=yau-tsim-mong-mong-kok&types=early-years&view=map',
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
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '3–6 years' }),
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
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument();
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
      screen.getByRole('heading', { name: 'How old is your child?' }),
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
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
  });

  it('can continue when the scope names no neighbourhood', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'atlantis';
    clearSearchAreaScopeCacheForTests();
    openNavigator();

    expect(screen.getByRole('status')).toHaveTextContent(
      'No areas are open yet',
    );
    expect(screen.getByRole('button', { name: /All areas/ })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    expect(
      screen.getByRole('heading', { name: 'How old is your child?' }),
    ).toBeInTheDocument();
  });

  it('does not write the starting choice into the search', () => {
    process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE = 'southern-stanley';
    clearSearchAreaScopeCacheForTests();
    const content = openNavigator();

    fireEvent.click(screen.getByRole('button', { name: 'Hong Kong Island' }));
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
    fireEvent.click(screen.getByRole('button', { name: '3–6 years' }));
    fireEvent.click(
      screen.getByRole('button', { name: content.smallWorld.navigator.seeActivitiesLabel }),
    );
    expect(push).toHaveBeenCalledWith('/en/search/?age=3-6&view=map');
  });
});
