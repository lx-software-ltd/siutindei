'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { AuthGate } from '../../../components/auth-gate';
import { AuthProvider } from '../../../components/auth-provider';
import { StatusBanner } from '../../../components/status-banner';

function ImportsRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/admin/dashboard?section=imports');
  }, [router]);

  return (
    <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
      <StatusBanner variant='info' kind='info'>
        Opening the imports section.
      </StatusBanner>
    </main>
  );
}

export default function AdminImportsPage() {
  return (
    <AuthProvider>
      <AuthGate>
        <ImportsRedirect />
      </AuthGate>
    </AuthProvider>
  );
}
