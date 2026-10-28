'use client';
import { formErrorClassName, RequiredMark } from './ui/admin-field-grid';
import { AdminInlineError } from './ui/admin-inline-error';

import { useState, type FormEvent } from 'react';

import { twMerge } from 'tailwind-merge';

import { useAuth } from './auth-provider';
import { AppleIcon, GoogleIcon } from './icons/action-icons';
import { LoginBackdrop } from './login/login-backdrop';
import { LoginBrandHeader } from './login/login-brand-header';
import { LoginFooter } from './login/login-footer';
import { StatusBanner } from './status-banner';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';

/** Taller than the console field. Input supplies the brand border and focus. */
const loginFieldSizeClassName = 'h-11 rounded-lg sm:h-11 sm:text-base';

const socialButtonClassName =
  'h-11 w-full justify-start gap-3 rounded-lg border-ink-900/15 text-sm font-semibold text-ink-900 hover:bg-brand-50 sm:h-11';

const primaryButtonClassName =
  'h-11 w-full rounded-lg text-base sm:h-11 sm:text-sm';

function loginFieldClass(invalid: boolean) {
  return twMerge(loginFieldSizeClassName, invalid ? formErrorClassName : '');
}

const socialProviders = [
  {
    key: 'google',
    label: 'Sign in with Google',
    provider: 'Google',
    Icon: GoogleIcon,
  },
  {
    key: 'apple',
    label: 'Sign in with Apple',
    provider: 'SignInWithApple',
    Icon: AppleIcon,
  },
] as const;

function isValidEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value);
}

export function LoginScreen() {
  const {
    login,
    configErrors,
    error,
    passwordlessStatus,
    passwordlessError,
    passwordlessEmail,
    sendPasswordlessCode,
    verifyPasswordlessCode,
    resetPasswordless,
  } = useAuth();

  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [emailTouched, setEmailTouched] = useState(false);
  const [codeTouched, setCodeTouched] = useState(false);
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const [codeSubmitted, setCodeSubmitted] = useState(false);

  const hasConfigErrors = configErrors.length > 0;
  const hasError = error.length > 0;
  const hasPasswordlessError = passwordlessError.length > 0;

  const isSending = passwordlessStatus === 'sending';
  const isVerifying = passwordlessStatus === 'verifying';
  const isLoading = isSending || isVerifying;
  const showCodeInput =
    passwordlessStatus === 'challenge' || passwordlessStatus === 'verifying';

  const trimmedEmail = email.trim();
  const emailError = !trimmedEmail
    ? 'Enter your work email.'
    : isValidEmail(trimmedEmail)
      ? ''
      : 'Enter a valid email address.';
  const showEmailError = Boolean(
    emailError && (emailTouched || emailSubmitted)
  );

  const trimmedCode = code.trim();
  const codeError = !trimmedCode
    ? 'Enter the verification code.'
    : /^[0-9]{6}$/.test(trimmedCode)
      ? ''
      : 'Enter the 6-digit code.';
  const showCodeError = Boolean(
    codeError && (codeTouched || codeSubmitted)
  );

  const handleEmailSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEmailSubmitted(true);
    setEmailTouched(true);
    await sendPasswordlessCode(email);
  };

  const handleCodeSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCodeSubmitted(true);
    setCodeTouched(true);
    await verifyPasswordlessCode(code);
  };

  const handleBackToEmail = () => {
    resetPasswordless();
    setCode('');
    setCodeTouched(false);
    setCodeSubmitted(false);
  };

  const handleProviderLogin = (provider: string) => {
    void login({ provider, returnTo: '/' });
  };

  return (
    <LoginBackdrop footer={<LoginFooter />}>
      <LoginBrandHeader
        subtitle='For the team that curates trusted classes, workshops, and outdoor adventures across Hong Kong.'
      />
      <Card className='w-full rounded-2xl border-brand-100 shadow-xl shadow-ink-900/10 sm:rounded-2xl sm:p-8'>
        {(hasError || hasConfigErrors || hasPasswordlessError) && (
          <div className='mb-4 space-y-2'>
            {hasError && (
              <StatusBanner kind='error'>
                {error}
              </StatusBanner>
            )}
            {hasPasswordlessError && (
              <StatusBanner kind='error'>
                {passwordlessError}
              </StatusBanner>
            )}
            {configErrors.map((configError) => (
              <StatusBanner
                key={configError}
                kind='error'
              >
                {configError}
              </StatusBanner>
            ))}
          </div>
        )}

        <div className='space-y-3'>
          {socialProviders.map(({ key, label, provider, Icon }) => (
            <Button
              key={key}
              type='button'
              variant='outline'
              onClick={() => handleProviderLogin(provider)}
              disabled={hasConfigErrors || isLoading}
              className={socialButtonClassName}
            >
              <span
                aria-hidden='true'
                className='flex h-5 w-5 items-center justify-center'
              >
                <Icon className='h-5 w-5' />
              </span>
              {label}
            </Button>
          ))}
        </div>

        <div className='relative my-6'>
          <div className='absolute inset-0 flex items-center'>
            <div className='w-full border-t border-brand-100' />
          </div>
          <div className='relative flex justify-center text-xs uppercase tracking-[0.3em] text-ink-700'>
            <span className='bg-white px-3'>Or</span>
          </div>
        </div>

        {!showCodeInput ? (
          <form onSubmit={handleEmailSubmit} className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='email'>
                Sign in with your email <RequiredMark />
              </Label>
              <Input
                id='email'
                type='email'
                placeholder='you@example.com'
                value={email}
                onChange={(event) => {
                  setEmailTouched(true);
                  setEmail(event.target.value);
                }}
                disabled={isLoading || hasConfigErrors}
                required
                autoComplete='email'
                autoFocus
                className={loginFieldClass(showEmailError)}
                aria-invalid={showEmailError || undefined}
              />
              {showEmailError ? (
                <AdminInlineError size='xs'>{emailError}</AdminInlineError>
              ) : null}
            </div>
            <Button
              type='submit'
              variant='brand'
              disabled={hasConfigErrors || !email.trim()}
              loading={isSending}
              loadingLabel='Sending link…'
              className={primaryButtonClassName}
            >
              Email me a magic link
            </Button>
            <p className='text-center text-xs text-ink-700'>
              We&apos;ll send a one-time code if links are blocked.
            </p>
          </form>
        ) : (
          <form onSubmit={handleCodeSubmit} className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='code'>
                Verification code <RequiredMark />
              </Label>
              <Input
                id='code'
                type='text'
                inputMode='numeric'
                pattern='[0-9]*'
                placeholder='123456'
                value={code}
                onChange={(event) => {
                  setCodeTouched(true);
                  setCode(event.target.value);
                }}
                disabled={isLoading}
                required
                autoComplete='one-time-code'
                autoFocus
                className={loginFieldClass(showCodeError)}
                aria-invalid={showCodeError || undefined}
              />
              {showCodeError ? (
                <AdminInlineError size='xs'>{codeError}</AdminInlineError>
              ) : null}
              <p className='text-xs text-ink-700'>
                Enter the 6-digit code sent to{' '}
                <span className='font-medium'>{passwordlessEmail}</span>
              </p>
            </div>
            <Button
              type='submit'
              variant='brand'
              disabled={!code.trim()}
              loading={isVerifying}
              loadingLabel='Verifying…'
              className={primaryButtonClassName}
            >
              Verify code
            </Button>
            <button
              type='button'
              onClick={handleBackToEmail}
              disabled={isLoading}
              className='w-full text-center text-sm text-ink-700 underline-offset-2 hover:text-ink-900 hover:underline disabled:opacity-50'
            >
              Use a different email
            </button>
          </form>
        )}

        <p className='mt-6 text-center text-xs text-ink-700'>
          You must be in the admin or manager group to access tools.
        </p>
      </Card>
    </LoginBackdrop>
  );
}
