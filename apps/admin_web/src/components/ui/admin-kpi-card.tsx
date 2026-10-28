import type { ReactNode } from 'react';

export interface AdminKpiCardProps {
  label: string;
  value: ReactNode;
}

/**
 * Count tile used above catalog-style tables. Every KPI uses the same
 * white card as the listing below it.
 */
export function AdminKpiCard({ label, value }: AdminKpiCardProps) {
  return (
    <div
      data-testid='admin-kpi-card'
      className='rounded-lg border border-brand-100 bg-white p-3 shadow-sm'
    >
      <p className='text-xs text-ink-500'>{label}</p>
      <p className='text-2xl font-semibold text-ink-900'>{value}</p>
    </div>
  );
}
