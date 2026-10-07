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
    <div className='rounded-lg border border-slate-200 bg-white p-3 shadow-sm'>
      <p className='text-xs text-slate-500'>{label}</p>
      <p className='text-2xl font-semibold text-slate-900'>{value}</p>
    </div>
  );
}
