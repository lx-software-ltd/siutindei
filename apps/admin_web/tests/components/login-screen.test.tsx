import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LoginScreen } from '@/components/login-screen';

const authState = {
  login: vi.fn(),
  configErrors: [] as string[],
  error: '',
  passwordlessStatus: 'idle' as
    | 'idle'
    | 'sending'
    | 'challenge'
    | 'verifying'
    | 'error',
  passwordlessError: '',
  passwordlessEmail: '',
  sendPasswordlessCode: vi.fn(),
  verifyPasswordlessCode: vi.fn(),
  resetPasswordless: vi.fn(),
};

vi.mock('@/components/auth-provider', () => ({
  useAuth: () => authState,
}));

vi.mock('@/lib/config', () => ({
  getPublicWwwUrl: () => 'https://example.test',
  getPrivacyPolicyUrl: () => 'https://example.test/privacy',
  getTermsOfUseUrl: () => 'https://example.test/terms',
}));

vi.mock('next/image', () => ({
  default: ({
    alt,
    src,
    className,
  }: {
    alt: string;
    src: string;
    className?: string;
  }) => <img alt={alt} src={src} className={className} />,
}));

describe('LoginScreen', () => {
  beforeEach(() => {
    authState.configErrors = [];
    authState.error = '';
    authState.passwordlessStatus = 'idle';
    authState.passwordlessError = '';
    authState.passwordlessEmail = '';
  });

  it('shows the Siu Tin Dei admin identity and the email form', () => {
    const { container } = render(<LoginScreen />);

    expect(
      screen.queryByRole('heading', {
        level: 1,
        name: 'Sign in to Siu Tin Dei Admin',
      })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
    expect(screen.getByText('Admin console')).toBeVisible();
    expect(screen.getByRole('img', { name: 'Siu Tin Dei' })).toHaveAttribute(
      'src',
      '/images/brand/siutindei-logo-stacked.svg'
    );
    expect(
      screen.getByRole('link', { name: 'Go to siutindei.com' })
    ).toHaveAttribute('href', 'https://example.test');
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute(
      'href',
      'https://example.test/privacy'
    );

    const bubbles = container.querySelectorAll(
      'img[src*="/images/small-world/"]'
    );
    expect(bubbles).toHaveLength(6);
    for (const bubble of bubbles) {
      expect(bubble).toHaveAttribute('aria-hidden', 'true');
    }

    const email = screen.getByLabelText(/Sign in with your email/);
    expect(email).toHaveClass('border-ink-900/15', 'focus:border-brand-700', 'focus:ring-brand-700');
    expect(email).not.toHaveClass('border-slate-300', 'focus:border-slate-500', 'focus:ring-brand-600');
    const label = container.querySelector('label[for="email"]');
    expect(label).toHaveClass('text-ink-900');
    expect(label).not.toHaveClass('text-slate-700');
    expect(
      screen.getByRole('button', { name: 'Email me a magic link' })
    ).toHaveClass('bg-accent-500', 'text-ink-900');
  });

  it('uses the red border once the email is invalid', async () => {
    authState.passwordlessStatus = 'idle';
    const user = userEvent.setup();

    render(<LoginScreen />);
    const email = screen.getByLabelText(/Sign in with your email/);
    await user.type(email, 'not-an-email');

    expect(email).toHaveClass('border-red-500', 'focus:border-red-500');
    expect(email).not.toHaveClass('border-ink-900/15', 'focus:border-brand-700');
  });

  it('shows configuration errors and disables sign-in', () => {
    authState.configErrors = ['NEXT_PUBLIC_COGNITO_DOMAIN is missing.'];

    render(<LoginScreen />);

    expect(
      screen.getByText('NEXT_PUBLIC_COGNITO_DOMAIN is missing.')
    ).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Sign in with Google' })
    ).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Sign in with Apple' })
    ).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Email me a magic link' })
    ).toBeDisabled();
    expect(screen.getByLabelText(/Sign in with your email/)).toBeDisabled();
  });

  it('keeps the verification step', () => {
    authState.passwordlessStatus = 'challenge';
    authState.passwordlessEmail = 'person@example.com';

    render(<LoginScreen />);

    expect(screen.getByLabelText(/Verification code/)).toBeVisible();
    expect(screen.getByText(/person@example.com/)).toBeVisible();
    expect(
      screen.getByRole('button', { name: 'Use a different email' })
    ).toBeVisible();
    expect(
      screen.queryByRole('button', { name: 'Email me a magic link' })
    ).not.toBeInTheDocument();
  });
});
