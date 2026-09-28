import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';

import { resetAdminQueryClientForTests } from '@/lib/admin-query-client';

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  resetAdminQueryClientForTests({ queries: { staleTime: 0 } });
});
