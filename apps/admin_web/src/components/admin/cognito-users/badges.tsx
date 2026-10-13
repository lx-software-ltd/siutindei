'use client';

import type { ReactNode } from 'react';

import {
  AppleIcon,
  EmailIcon,
  GoogleIcon,
} from '../../icons/action-icons';
import { StatusBadge } from '../../ui/status-badge';

export const USER_ROLES = ['admin', 'manager'] as const;

export type UserRole = (typeof USER_ROLES)[number];

export function formatRoleLabel(role: string): string {
  return role.charAt(0).toUpperCase() + role.slice(1);
}

export function assignedUserRoles(groups: string[] | null | undefined): UserRole[] {
  return USER_ROLES.filter((role) => groups?.includes(role));
}

export function RoleBadge({ role }: { role: UserRole }) {
  const tone = role === 'admin' ? 'purple' : 'blue';

  return <StatusBadge status={role} tone={tone} label={formatRoleLabel(role)} />;
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
    <span role='img' title={provider} aria-label={provider} className='inline-flex items-center'>
      {icons[provider]}
    </span>
  );
}
