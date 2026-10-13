import type { ReactNode } from 'react';

import { Card } from './card';

export interface AdminKpiCardProps {
  label: string;
  value: ReactNode;
}

/**
 * Count tile used above catalog-style tables. Same `Card` surface as
 * listings and forms.
 */
export function AdminKpiCard({ label, value }: AdminKpiCardProps) {
  return (
    <Card data-testid='admin-kpi-card'>
      <p className='text-xs text-slate-500'>{label}</p>
      <p className='text-2xl font-semibold text-slate-900'>{value}</p>
    </Card>
  );
}
