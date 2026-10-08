'use client';

import type { ReactNode } from 'react';

import {
  AppleIcon,
  EmailIcon,
  GoogleIcon,
} from '../../icons/action-icons';
import { StatusBadge } from '../../ui/status-badge';

export function RoleBadge({
  role,
  isActive,
}: {
  role: 'admin' | 'manager';
  isActive: boolean;
}) {
  const tone = !isActive ? 'slate' : role === 'admin' ? 'purple' : 'blue';
  const label = role.charAt(0).toUpperCase() + role.slice(1);

  return <StatusBadge status={role} tone={tone} label={label} />;
}

type IdentityProvider = 'Google' | 'Apple' | 'Email';

function getIdentityProvider(
  username: string | null | undefined
): IdentityProvider {
  if (!username) return 'Email';
  const lowerUsername = username.toLowerCase();
  if (lowerUsername.startsWith('google_')) return 'Google';
  if (lowerUsername.startsWith('signinwithapple_')) return 'Apple';
  return 'Email';
}

export function IdentityProviderBadge({
  username,
}: {
  username: string | null | undefined;
}) {
  const provider = getIdentityProvider(username);

  const icons: Record<IdentityProvider, ReactNode> = {
    Google: <GoogleIcon className='h-4 w-4' />,
    Apple: <AppleIcon className='h-4 w-4' />,
    Email: <EmailIcon className='h-4 w-4 text-slate-500' />,
  };

  return (
    <span title={provider} className='inline-flex items-center'>
      {icons[provider]}
    </span>
  );
}
