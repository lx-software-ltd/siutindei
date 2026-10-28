'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { AuthGate } from '../../../components/auth-gate';
import { AuthProvider } from '../../../components/auth-provider';
import { LoginBackdrop } from '../../../components/login/login-backdrop';
import { LoginBrandHeader } from '../../../components/login/login-brand-header';
import { StatusBanner } from '../../../components/status-banner';

function ImportsRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/admin/dashboard?section=imports');
  }, [router]);

  return (
    <LoginBackdrop>
      <LoginBrandHeader />
      <StatusBanner kind='info'>
        Opening the imports section.
      </StatusBanner>
    </LoginBackdrop>
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
