import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import AuthCallbackPage from '@/app/auth/callback/page';
import { ADMIN_SESSION_LOADING_COPY } from '@/components/login/login-loading-notice';

const completeLogin = vi.hoisted(() => vi.fn());

vi.mock('@/lib/auth', () => ({
  completeLogin,
}));

vi.mock('next/image', () => ({
  default: ({ alt, src }: { alt: string; src: string }) => (
    <img alt={alt} src={src} />
  ),
}));

describe('Auth callback session notice', () => {
  it('shows the bao notice on the login backdrop while the code is exchanged', () => {
    completeLogin.mockReturnValue(new Promise(() => undefined));

    render(<AuthCallbackPage />);

    expect(screen.getByRole('status')).toHaveTextContent(
      ADMIN_SESSION_LOADING_COPY
    );
    expect(screen.queryByText('Info')).not.toBeInTheDocument();
    expect(screen.queryByText('Signing you in...')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).not.toHaveClass('bg-white');
    expect(document.querySelector('.admin-login-hero')).not.toBeNull();
    expect(screen.getByRole('img', { name: 'Siu Tin Dei' })).toBeVisible();
    expect(
      document.querySelector('img.admin-login-bao')
    ).toHaveAttribute('src', '/images/small-world/bubble-bao.webp');
  });

  it('keeps the login-failed banner when the exchange fails', async () => {
    completeLogin.mockRejectedValue(
      new Error('Authorization code is missing.')
    );

    render(<AuthCallbackPage />);

    expect(await screen.findByText('Login failed')).toBeVisible();
    expect(screen.getByText('Authorization code is missing.')).toBeVisible();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(document.querySelector('img.admin-login-bao')).toBeNull();
    expect(document.querySelector('.admin-login-hero')).toBeNull();
  });
});
