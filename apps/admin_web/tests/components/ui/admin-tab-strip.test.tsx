import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  AdminTabStrip,
  formatAdminTabLabel,
} from '@/components/ui/admin-tab-strip';

describe('formatAdminTabLabel', () => {
  it('uses sentence case and keeps all-caps tokens', () => {
    expect(formatAdminTabLabel('Category checks')).toBe('Category checks');
    expect(formatAdminTabLabel('feedback labels')).toBe('Feedback labels');
    expect(formatAdminTabLabel('API keys')).toBe('API keys');
    expect(formatAdminTabLabel('Suggestions')).toBe('Suggestions');
  });
});

describe('AdminTabStrip', () => {
  it('renders tab labels in sentence case', () => {
    render(
      <AdminTabStrip
        aria-label='Categories'
        items={[
          { key: 'categories', label: 'Categories' },
          { key: 'checks', label: 'Category checks' },
        ]}
        activeKey='categories'
        onChange={vi.fn()}
      />
    );

    expect(
      screen.getByRole('button', { name: 'Category checks' })
    ).toBeVisible();
  });
});
