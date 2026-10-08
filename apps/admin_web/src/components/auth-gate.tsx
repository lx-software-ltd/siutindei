'use client';

import type { ReactNode } from 'react';

import { useAuth } from './auth-provider';
import { LoginScreen } from './login-screen';
import { StatusBanner } from './status-banner';

interface AuthGateProps {
  children: ReactNode;
  requireAuth?: boolean;
  /**
   * Rendered on public routes after sign-in. Do not router-replace to
   * `/admin/dashboard`: admin-web CloudFront maps unknown paths to
   * `/index.html`, which rehydrates this gate and loops on Redirecting.
   */
  signedIn?: ReactNode;
}

export function AuthGate({
  children,
  requireAuth = true,
  signedIn,
}: AuthGateProps) {
  const { status } = useAuth();

  if (status === 'loading') {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <StatusBanner variant='info' kind='info'>
          Preparing your admin session.
        </StatusBanner>
      </main>
    );
  }

  if (status === 'unauthenticated') {
    return requireAuth ? <LoginScreen /> : <>{children}</>;
  }

  if (!requireAuth) {
    return <>{signedIn ?? children}</>;
  }

  return <>{children}</>;
}
