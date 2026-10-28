'use client';

import type { ReactNode } from 'react';

import { useAuth } from './auth-provider';
import { LoginBackdrop } from './login/login-backdrop';
import { LoginBrandHeader } from './login/login-brand-header';
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
      <LoginBackdrop>
        <LoginBrandHeader />
        <StatusBanner kind='info'>
          Preparing your admin session.
        </StatusBanner>
      </LoginBackdrop>
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
