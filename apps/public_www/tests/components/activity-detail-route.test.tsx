import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ActivityDetailRoute } from '@/components/pages/activity-detail-route';
import { getContent } from '@/content';
import { fetchActivityListingById } from '@/lib/activities/search-client';

const currentSearchParams = vi.hoisted(() => ({
  value: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => currentSearchParams.value,
}));

vi.mock('@/lib/activities/search-client', () => ({
  fetchActivityListingById: vi.fn(),
  fetchActivitySearch: vi.fn(),
}));

const copy = getContent('zh-HK').activityDetail;

describe('ActivityDetailRoute', () => {
  beforeEach(() => {
    currentSearchParams.value = new URLSearchParams();
    vi.mocked(fetchActivityListingById).mockReset();
  });

  it('shows the missing-activity state when the link has no id', () => {
    render(<ActivityDetailRoute locale="zh-HK" copy={copy} />);

    expect(
      screen.getByRole('heading', { level: 1, name: copy.notFoundLabel }),
    ).toBeInTheDocument();
    expect(screen.getByText(copy.notFoundHint)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: copy.browseActivitiesLabel })).toHaveAttribute(
      'href',
      '/zh-HK/search?view=list',
    );
    expect(fetchActivityListingById).not.toHaveBeenCalled();
  });
});
