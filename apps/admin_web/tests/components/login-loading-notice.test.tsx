import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  ADMIN_SESSION_LOADING_COPY,
  LoginLoadingNotice,
} from '@/components/login/login-loading-notice';

describe('LoginLoadingNotice', () => {
  it('puts a decorative spinning bao to the left of one sentence', () => {
    render(<LoginLoadingNotice />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent(ADMIN_SESSION_LOADING_COPY);
    expect(status).toHaveClass('justify-center');
    expect(status).not.toHaveClass('bg-white', 'border', 'border-brand-200');
    expect(screen.queryByText('Info')).not.toBeInTheDocument();

    const bao = status.querySelector('img');
    expect(bao).toBe(status.firstElementChild);
    expect(bao).toHaveAttribute('src', '/images/small-world/bubble-bao.webp');
    expect(bao).toHaveAttribute('alt', '');
    expect(bao).toHaveAttribute('aria-hidden', 'true');
    expect(bao).toHaveClass('admin-login-bao');
  });
});
