import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { usePrefetchAdminSection } from '@/hooks/use-prefetch-admin-section';
import { getResourceApi } from '@/lib/resource-api';

describe('usePrefetchAdminSection', () => {
  it('does not throw when a manager hovers the feedback section', () => {
    expect(() => getResourceApi('organization-feedback', 'manager')).toThrow(/Unknown resource type/);
    const { result } = renderHook(() => usePrefetchAdminSection('manager'));
    expect(() => result.current('feedback')).not.toThrow();
  });
});
