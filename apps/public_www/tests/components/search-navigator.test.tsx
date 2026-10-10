import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SearchNavigator } from '@/components/sections/hero/search-navigator';
import { SearchProvider } from '@/components/shared/search/search-context';
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
});
