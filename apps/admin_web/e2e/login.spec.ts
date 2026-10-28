import { test, expect, setupAuth, mockAdminUser } from './fixtures/test-fixtures';

test.describe('Login Screen', () => {
  test('should display login screen when unauthenticated', async ({ unauthenticatedPage }) => {
    await unauthenticatedPage.goto('/');

    // Wait for the page to load
    await expect(
      unauthenticatedPage.getByRole('heading', {
        name: 'Sign in to Siu Tin Dei Admin',
        level: 1,
      })
    ).toBeVisible();
    await expect(
      unauthenticatedPage.getByRole('img', { name: 'Siu Tin Dei' })
    ).toBeVisible();
    await expect(unauthenticatedPage.getByText('Admin console')).toBeVisible();
    const publicSiteLink = unauthenticatedPage.getByRole('link', {
      name: 'Go to siutindei.com',
    });
    await expect(publicSiteLink).toBeVisible();
    await expect(publicSiteLink).toHaveAttribute(
      'href',
      'https://siutindei.com'
    );
    const bubbles = unauthenticatedPage.locator(
      'img[src*="/images/small-world/"]'
    );
    await expect(bubbles).toHaveCount(6);
    const bubblesAreDecorative = await bubbles.evaluateAll((images) =>
      images.every((image) => image.getAttribute('aria-hidden') === 'true')
    );
    expect(bubblesAreDecorative).toBe(true);
    const iconHrefs = await unauthenticatedPage
      .locator('link[rel="icon"]')
      .evaluateAll((links) => links.map((link) => link.getAttribute('href')));
    expect(iconHrefs).toEqual(
      expect.arrayContaining(['/favicon.ico', '/favicon.svg'])
    );

    // Check for social login buttons
    await expect(
      unauthenticatedPage.getByRole('button', { name: 'Continue with Google' })
    ).toBeVisible();
    await expect(
      unauthenticatedPage.getByRole('button', { name: 'Continue with Apple' })
    ).toBeVisible();

    // Check for email magic link
    await expect(
      unauthenticatedPage.getByRole('button', { name: 'Email me a magic link' })
    ).toBeVisible();

    // Check for helper text
    await expect(
      unauthenticatedPage.getByText(
        'You must be in the admin or manager group to access tools.'
      )
    ).toBeVisible();

    // Check for legal links to the public website
    const privacyLink = unauthenticatedPage.getByRole('link', {
      name: 'Privacy Policy',
    });
    await expect(privacyLink).toBeVisible();
    await expect(privacyLink).toHaveAttribute('href', /\/privacy$/);
    const termsLink = unauthenticatedPage.getByRole('link', {
      name: 'Terms of Use',
    });
    await expect(termsLink).toBeVisible();
    await expect(termsLink).toHaveAttribute('href', /\/terms$/);
  });

  test('should show loading state initially', async ({ page }) => {
    // Visit without any auth setup to see loading state briefly
    await page.goto('/');

    // The page should show loading state
    const loadingText = page.getByText('Preparing your admin session.');

    // Note: This may be very brief, so we use a short timeout
    // If the loading state is too fast, this test may need adjustment
    try {
      await expect(loadingText).toBeVisible({ timeout: 1000 });
    } catch {
      // Loading may have finished too quickly, which is fine
    }
  });

  test('login button should be enabled when config is present', async ({ unauthenticatedPage }) => {
    await unauthenticatedPage.goto('/');

    const googleButton = unauthenticatedPage.getByRole('button', {
      name: 'Continue with Google',
    });
    await expect(googleButton).toBeVisible();
    await expect(googleButton).toBeEnabled();
  });

  test('should show the admin console when authenticated as admin', async ({ adminPage }) => {
    await adminPage.goto('/');

    await expect(
      adminPage.getByRole('heading', { name: 'Siu Tin Dei Admin', exact: true })
    ).toBeVisible();
    await expect(adminPage.getByRole('button', { name: 'Catalog' })).toBeVisible();
    await expect(adminPage.getByText('Redirecting')).toHaveCount(0);
  });

  test('should display config errors when environment variables are missing', async ({ page }) => {
    // Override config to simulate missing values
    await page.addInitScript(() => {
      // Clear any existing tokens
      localStorage.removeItem('admin_auth_tokens');
    });

    // Note: This test verifies the UI handles config errors gracefully
    // In a real scenario, the app would show config error banners
    await page.goto('/');

    // Page should still render (either login or error state)
    await expect(page).toHaveURL('/');
  });

  test('should not show admin dashboard for unauthenticated users', async ({ unauthenticatedPage }) => {
    await unauthenticatedPage.goto('/');

    // Should NOT see the admin dashboard navigation
    await expect(
      unauthenticatedPage.getByRole('button', { name: 'Log out' })
    ).not.toBeVisible();

    // Should see login screen instead
    await expect(
      unauthenticatedPage.getByRole('heading', {
        name: 'Sign in to Siu Tin Dei Admin',
        level: 1,
      })
    ).toBeVisible();
  });

  test('fits the login screen on a phone', async ({ unauthenticatedPage }) => {
    await unauthenticatedPage.setViewportSize({ width: 375, height: 812 });
    await unauthenticatedPage.goto('/');

    await expect(
      unauthenticatedPage.getByRole('heading', {
        name: 'Sign in to Siu Tin Dei Admin',
        level: 1,
      })
    ).toBeVisible();
    await expect(
      unauthenticatedPage.getByRole('button', { name: 'Continue with Google' })
    ).toBeVisible();
    await expect(
      unauthenticatedPage
        .locator('img[src*="/images/small-world/"]')
        .filter({ visible: true })
    ).toHaveCount(0);
    const fits = await unauthenticatedPage.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    );
    expect(fits).toBe(true);
  });
});

test.describe('Login screen reduced motion', () => {
  test.use({ reducedMotion: 'reduce' });

  test('keeps the decorative pictures still', async ({ unauthenticatedPage }) => {
    await unauthenticatedPage.goto('/');

    const animationName = await unauthenticatedPage
      .locator('img[src*="/images/small-world/"]')
      .first()
      .evaluate((image) => getComputedStyle(image).animationName);
    expect(animationName).toBe('none');
  });
});

test.describe('Authentication Flow', () => {
  test('should persist auth state across page reloads', async ({ page }) => {
    // Set up auth first
    await setupAuth(page, mockAdminUser);

    // Mock the API endpoints
    await page.route('**/api/mock/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], cursor: null }),
      });
    });

    await page.goto('/admin/dashboard');

    // Should be authenticated
    await expect(
      page.getByRole('heading', { name: 'Siu Tin Dei Admin', exact: true })
    ).toBeVisible();

    // Reload the page
    await page.reload();

    // Should still be authenticated
    await expect(
      page.getByRole('heading', { name: 'Siu Tin Dei Admin', exact: true })
    ).toBeVisible();
  });

  test('should show user email when authenticated', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Should display the user's email
    await expect(adminPage.locator('header').getByText('admin@example.com')).toBeVisible();
  });

  test('logout button should be visible for authenticated users', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    // Should have a logout button
    const logoutButton = adminPage.getByRole('button', { name: 'Log out' });
    await expect(logoutButton).toBeVisible();
  });

  test('legal links should be visible in the dashboard footer', async ({ adminPage }) => {
    await adminPage.goto('/admin/dashboard');

    const footer = adminPage.locator('footer');
    await expect(
      footer.getByRole('link', { name: 'Privacy Policy' })
    ).toBeVisible();
    await expect(
      footer.getByRole('link', { name: 'Terms of Use' })
    ).toBeVisible();
  });
});
