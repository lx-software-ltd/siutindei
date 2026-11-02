'use client';

import type { CognitoUser } from 'amazon-cognito-identity-js';
import type { ReactNode } from 'react';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import {
  completeLogin,
  ensureFreshTokens,
  getUserProfile,
  startLogin,
  startLogout,
  storeTokensFromPasswordless,
  type LoginOptions,
} from '../lib/auth';
import { getConfigErrors } from '../lib/config';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

export type PasswordlessStatus =
  | 'idle'
  | 'sending'
  | 'challenge'
  | 'verifying'
  | 'error';

export interface AuthContextValue {
  status: AuthStatus;
  user: ReturnType<typeof getUserProfile> | null;
  isAdmin: boolean;
  isManager: boolean;
  configErrors: string[];
  error: string;
  login: (options?: LoginOptions) => Promise<void>;
  logout: () => void;
  // Passwordless auth
  passwordlessStatus: PasswordlessStatus;
  passwordlessError: string;
  passwordlessEmail: string;
  sendPasswordlessCode: (email: string) => Promise<void>;
  verifyPasswordlessCode: (code: string) => Promise<void>;
  resetPasswordless: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<AuthContextValue['user']>(null);
  const [error, setError] = useState('');
  const configErrors = useMemo(() => getConfigErrors(), []);

  // Passwordless state
  const [passwordlessStatus, setPasswordlessStatus] =
    useState<PasswordlessStatus>('idle');
  const [passwordlessError, setPasswordlessError] = useState('');
  const [passwordlessEmail, setPasswordlessEmail] = useState('');
  const [cognitoUser, setCognitoUser] = useState<CognitoUser | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadSession = async () => {
      if (configErrors.length > 0) {
        if (isMounted) {
          setStatus('unauthenticated');
        }
        return;
      }
      try {
        let tokens = await ensureFreshTokens();
        if (typeof window !== 'undefined') {
          const url = new URL(window.location.href);
          if (!tokens && url.searchParams.has('code')) {
            const redirectPath = await completeLogin();
            if (!isMounted) {
              return;
            }
            tokens = await ensureFreshTokens();
            if (!isMounted) {
              return;
            }
            if (redirectPath !== url.pathname) {
              window.location.replace(redirectPath);
              return;
            }
          }
        }
        if (!isMounted) {
          return;
        }
        if (tokens) {
          const profile = getUserProfile(tokens);
          setError('');
          setUser(profile);
          setStatus('authenticated');
        } else {
          setStatus('unauthenticated');
        }
      } catch (err) {
        if (!isMounted) {
          return;
        }
        const message =
          err instanceof Error ? err.message : 'Unable to load session.';
        setError(message);
        setStatus('unauthenticated');
      }
    };

    loadSession();

    return () => {
      isMounted = false;
    };
  }, [configErrors]);

  const login = async (options?: LoginOptions) => {
    await startLogin(options);
  };

  const logout = () => {
    startLogout();
  };

  const sendPasswordlessCode = async (email: string) => {
    const normalizedEmail = email.toLowerCase().trim();
    if (!normalizedEmail) {
      setPasswordlessError('Please enter your email address.');
      setPasswordlessStatus('error');
      return;
    }

    setPasswordlessEmail(normalizedEmail);
    setPasswordlessError('');
    setPasswordlessStatus('sending');

    try {
      const passwordless = await import('../lib/cognito-auth');
      await passwordless.signUpPasswordlessUser(normalizedEmail);
      const user = await passwordless.initiatePasswordlessSignIn(normalizedEmail);
      setCognitoUser(user);
      setPasswordlessStatus('challenge');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to send verification code.';
      setPasswordlessError(message);
      setPasswordlessStatus('error');
    }
  };

  const verifyPasswordlessCode = async (code: string) => {
    if (!cognitoUser) {
      setPasswordlessError('Session expired. Please request a new code.');
      setPasswordlessStatus('error');
      return;
    }

    const trimmedCode = code.trim();
    if (!trimmedCode) {
      setPasswordlessError('Please enter the verification code.');
      setPasswordlessStatus('error');
      return;
    }

    setPasswordlessError('');
    setPasswordlessStatus('verifying');

    try {
      const passwordless = await import('../lib/cognito-auth');
      const tokens = await passwordless.respondToPasswordlessChallenge(
        cognitoUser,
        trimmedCode,
      );

      // Store tokens and update auth state
      storeTokensFromPasswordless(tokens);
      const profile = getUserProfile({
        accessToken: tokens.accessToken,
        idToken: tokens.idToken,
        refreshToken: tokens.refreshToken,
        expiresAt: tokens.expiresAt,
      });

      setUser(profile);
      setStatus('authenticated');
      setPasswordlessStatus('idle');
      setCognitoUser(null);
      setPasswordlessEmail('');
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to verify code.';
      setPasswordlessError(message);
      setPasswordlessStatus('challenge'); // Stay in challenge state to allow retry
    }
  };

  const resetPasswordless = () => {
    setPasswordlessStatus('idle');
    setPasswordlessError('');
    setPasswordlessEmail('');
    setCognitoUser(null);
  };

  const isAdmin = Boolean(user?.groups?.includes('admin'));
  const isManager = Boolean(user?.groups?.includes('manager'));

  const value: AuthContextValue = {
    status,
    user,
    isAdmin,
    isManager,
    configErrors,
    error,
    login,
    logout,
    passwordlessStatus,
    passwordlessError,
    passwordlessEmail,
    sendPasswordlessCode,
    verifyPasswordlessCode,
    resetPasswordless,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider.');
  }
  return context;
}
