import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CategorySuggestionSettingsCard } from '@/components/admin/category-suggestions/settings-card';
import { getCategorySuggestionSettings } from '@/lib/api-client-category-suggestions';

vi.mock('@/lib/api-client-category-suggestions', () => ({
  getCategorySuggestionSettings: vi.fn(),
  updateCategorySuggestionSettings: vi.fn(),
  testCategorySuggestionModel: vi.fn(),
}));

describe('CategorySuggestionSettingsCard', () => {
  beforeEach(() => {
    vi.mocked(getCategorySuggestionSettings).mockRejectedValue(
      new Error('Settings failed.')
    );
  });

  it('shows the load error instead of a permanent loading line', async () => {
    render(<CategorySuggestionSettingsCard />);

    expect(await screen.findByText('Settings failed.')).toBeVisible();
    expect(screen.queryByText('Loading settings...')).not.toBeInTheDocument();
    expect(screen.queryByTestId('admin-input-card-bar')).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Suggestion settings', level: 3 })
    ).toBeVisible();
  });
});
