'use client';

import dynamic from 'next/dynamic';
import type { ComponentType } from 'react';

import { AdminSkeleton } from '@/components/ui/admin-skeleton';

/** Placeholder while a dashboard section chunk loads. Uses the shared shimmer. */
export function DashboardSectionFallback() {
  return (
    <div className='space-y-3' aria-busy='true'>
      <AdminSkeleton className='h-8 w-48' />
      <AdminSkeleton className='h-10 w-full' />
      <AdminSkeleton className='h-64 w-full' />
    </div>
  );
}

export function loadDashboardSection<P extends object>(loader: () => Promise<ComponentType<P>>) {
  return dynamic(loader, {
    loading: () => <DashboardSectionFallback />,
  });
}
