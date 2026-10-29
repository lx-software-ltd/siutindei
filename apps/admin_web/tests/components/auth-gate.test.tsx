import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { AuthGate } from '@/components/auth-gate';
import { ADMIN_SESSION_LOADING_COPY } from '@/components/login/login-loading-notice';

const replace = vi.fn();
const authState = {
  status: 'unauthenticated' as 'loading' | 'authenticated' | 'unauthenticated',
};

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
}));

vi.mock('@/components/auth-provider', () => ({
  useAuth: () => authState,
}));

vi.mock('@/components/login-screen', () => ({
  LoginScreen: () => <div>Login screen</div>,
}));

vi.mock('next/image', () => ({
  default: ({
    alt,
    src,
  }: {
    alt: string;
    src: string;
  }) => <img alt={alt} src={src} />,
}));

describe('AuthGate', () => {
  it('shows the signed-in view on a public route without redirecting', () => {
    authState.status = 'authenticated';

    render(
      <AuthGate requireAuth={false} signedIn={<div>Admin console</div>}>
        <div>Login screen child</div>
      </AuthGate>
    );

    expect(screen.getByText('Admin console')).toBeVisible();
    expect(screen.queryByText('Redirecting')).not.toBeInTheDocument();
    expect(screen.queryByText('Login screen child')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('brands the loading state with the Siu Tin Dei mark', () => {
    authState.status = 'loading';

    render(
      <AuthGate>
        <div>Protected console</div>
      </AuthGate>
    );

    expect(screen.getByRole('status')).toHaveTextContent(
      ADMIN_SESSION_LOADING_COPY
    );
    expect(screen.queryByText('Info')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).not.toHaveClass('bg-white');
    expect(document.querySelector('img.admin-login-bao')).toHaveAttribute(
      'src',
      '/images/small-world/bubble-bao.webp'
    );
    expect(screen.getByRole('img', { name: 'Siu Tin Dei' })).toBeVisible();
    expect(screen.getByText('Admin console')).toBeVisible();
    expect(screen.queryByText('Protected console')).not.toBeInTheDocument();
  });

  it('shows the login screen on a public route when signed out', () => {
    authState.status = 'unauthenticated';

    render(
      <AuthGate requireAuth={false} signedIn={<div>Admin console</div>}>
        <div>Login screen child</div>
      </AuthGate>
    );

    expect(screen.getByText('Login screen child')).toBeVisible();
    expect(screen.queryByText('Admin console')).not.toBeInTheDocument();
    expect(screen.queryByText('Redirecting')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('keeps a protected route on the login screen instead of bouncing home', () => {
    authState.status = 'unauthenticated';

    render(
      <AuthGate>
        <div>Protected console</div>
      </AuthGate>
    );

    expect(screen.getByText('Login screen')).toBeVisible();
    expect(screen.queryByText('Protected console')).not.toBeInTheDocument();
    expect(screen.queryByText('Redirecting')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('shows a protected route after sign-in without a Redirecting banner', () => {
    authState.status = 'authenticated';

    render(
      <AuthGate>
        <div>Protected console</div>
      </AuthGate>
    );

    expect(screen.getByText('Protected console')).toBeVisible();
    expect(screen.queryByText('Redirecting')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
