import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  AdminTabStrip,
  formatAdminTabLabel,
} from '@/components/ui/admin-tab-strip';

describe('formatAdminTabLabel', () => {
  it('capitalizes the first letter of every word', () => {
    expect(formatAdminTabLabel('Category checks')).toBe('Category Checks');
    expect(formatAdminTabLabel('feedback labels')).toBe('Feedback Labels');
    expect(formatAdminTabLabel('Category Suggestions')).toBe(
      'Category Suggestions'
    );
  });
});

describe('AdminTabStrip', () => {
  it('renders tab labels in Title Case', () => {
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
      screen.getByRole('button', { name: 'Category Checks' })
    ).toBeVisible();
  });
});
