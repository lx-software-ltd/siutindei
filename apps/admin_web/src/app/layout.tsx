import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import { NuqsAdapter } from 'nuqs/adapters/next/app';

import { AdminQueryProvider } from '@/components/admin-query-provider';

import './globals.css';

export const metadata: Metadata = {
  title: 'Siu Tin Dei Admin',
  description: 'Admin tools for managing activities data.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang='en'>
      <body className='antialiased'>
        <NuqsAdapter>
          <AdminQueryProvider>{children}</AdminQueryProvider>
        </NuqsAdapter>
      </body>
    </html>
  );
}
