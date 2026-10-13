import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AuditHighlightedJson } from '@/components/admin/audit-highlighted-json';

describe('AuditHighlightedJson', () => {
  it('uses a darker background on changed tokens', () => {
    render(
      <AuditHighlightedJson
        aria-label='Old values JSON'
        className='bg-red-50'
        emphasisClassName='bg-red-300'
        value={{ first_name: 'Ann', last_name: 'Lee' }}
        counterpart={{ first_name: 'Anne', last_name: 'Lee' }}
      />
    );

    const oldJson = screen.getByLabelText('Old values JSON');
    const changedName = within(oldJson).getByText('"first_name"');
    const changedValue = within(oldJson).getByText('Ann');

    expect(changedName).toHaveAttribute('data-audit-changed', 'true');
    expect(changedName).toHaveClass('bg-red-300');
    expect(changedValue).toHaveAttribute('data-audit-changed', 'true');
    expect(changedValue).toHaveClass('bg-red-300');
    expect(
      within(oldJson).queryByText('"last_name"', {
        selector: '[data-audit-changed="true"]',
      })
    ).toBeNull();
  });
});
