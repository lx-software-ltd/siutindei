import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AdminKpiCard } from '@/components/ui/admin-kpi-card';
import { AdminDataTableHeadCell } from '@/components/ui/admin-data-table';
import { AdminRecordTable } from '@/components/ui/admin-record-table';
import { Card, cardSurfaceClass } from '@/components/ui/card';

function expectCardSurface(element: HTMLElement) {
  for (const token of cardSurfaceClass.split(/\s+/)) {
    expect(element).toHaveClass(token);
  }
}

describe('Card', () => {
  it('uses the shared surface class for a titled form card', () => {
    render(<Card title='Suggestion settings'>Fields</Card>);

    expectCardSurface(screen.getByRole('heading', { name: 'Suggestion settings' }).closest('section')!);
  });
});

describe('shared card surface', () => {
  it('is the same class on tables, KPI tiles, and titled cards', () => {
    render(
      <>
        <AdminRecordTable
          aria-label='Catalog'
          columnCount={1}
          rowCount={0}
          isLoading={false}
          head={<AdminDataTableHeadCell>Name</AdminDataTableHeadCell>}
        >
          {null}
        </AdminRecordTable>
        <AdminKpiCard label='Pending review' value={1} />
        <Card title='Rules'>Settings</Card>
      </>
    );

    expectCardSurface(screen.getByTestId('admin-record-table'));
    expectCardSurface(screen.getByTestId('admin-kpi-card'));
    expectCardSurface(screen.getByRole('heading', { name: 'Rules' }).closest('section')!);
  });
});
