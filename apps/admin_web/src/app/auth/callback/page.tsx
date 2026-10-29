'use client';

import { useEffect, useState } from 'react';

import { LoginBackdrop } from '../../../components/login/login-backdrop';
import { LoginBrandHeader } from '../../../components/login/login-brand-header';
import { LoginLoadingNotice } from '../../../components/login/login-loading-notice';
import { StatusBanner } from '../../../components/status-banner';
import { completeLogin } from '../../../lib/auth';

export default function AuthCallbackPage() {
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    let isMounted = true;

    const finishLogin = async () => {
      try {
        const redirectPath = await completeLogin();
        window.location.replace(redirectPath);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        const message =
          error instanceof Error
            ? error.message
            : 'Unable to complete login.';
        setErrorMessage(message);
      }
    };

    finishLogin();

    return () => {
      isMounted = false;
    };
  }, []);

  if (errorMessage) {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <StatusBanner variant='error' title='Login failed'>
          {errorMessage}
        </StatusBanner>
      </main>
    );
  }

  return (
    <LoginBackdrop>
      <LoginBrandHeader />
      <LoginLoadingNotice />
    </LoginBackdrop>
  );
}
