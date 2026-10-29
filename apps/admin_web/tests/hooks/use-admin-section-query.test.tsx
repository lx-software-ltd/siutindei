import { act, renderHook, waitFor } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { useAdminSectionQuery } from '@/hooks/use-admin-section-query';

const sections = [{ key: 'organizations' }, { key: 'locations' }, { key: 'media' }];

describe('useAdminSectionQuery', () => {
  it('removes record params that the active section does not read', async () => {
    const updates: string[] = [];
    renderHook(() => useAdminSectionQuery(sections, 'organizations'), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <NuqsTestingAdapter
          hasMemory
          searchParams='?section=organizations&location=loc-1'
          onUrlUpdate={(event) => updates.push(event.queryString)}
        >
          {children}
        </NuqsTestingAdapter>
      ),
    });

    await waitFor(() => expect(updates.length).toBeGreaterThan(0));
    expect(updates.at(-1)).toContain('section=organizations');
    expect(updates.at(-1)).not.toContain('location=');
  });

  it('keeps a legacy edit link on the organizations section', async () => {
    const updates: string[] = [];
    renderHook(() => useAdminSectionQuery(sections, 'organizations'), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <NuqsTestingAdapter
          hasMemory
          searchParams='?edit=org-1&ticket=t-1'
          onUrlUpdate={(event) => updates.push(event.queryString)}
        >
          {children}
        </NuqsTestingAdapter>
      ),
    });

    await waitFor(() => expect(updates.some((query) => query.includes('section=organizations'))).toBe(true));
    const latest = updates.at(-1) ?? '';
    expect(latest).toContain('edit=org-1');
    expect(latest).not.toContain('ticket=');
  });

  it('clears the previous record when the operator changes section', async () => {
    const updates: string[] = [];
    const { result } = renderHook(() => useAdminSectionQuery(sections, 'organizations'), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <NuqsTestingAdapter
          hasMemory
          searchParams='?section=organizations&organization=org-1'
          onUrlUpdate={(event) => updates.push(event.queryString)}
        >
          {children}
        </NuqsTestingAdapter>
      ),
    });

    act(() => {
      result.current.selectSection('locations');
    });

    await waitFor(() => expect(updates.at(-1) ?? '').toContain('section=locations'));
    expect(updates.at(-1)).not.toContain('organization=');
  });

  it('keeps a preserved org when the section does not list it', async () => {
    const managerSections = [
      { key: 'organizations' },
      { key: 'suggest-place' },
      { key: 'feedback' },
    ];
    const updates: string[] = [];
    const { result } = renderHook(
      () => useAdminSectionQuery(managerSections, 'organizations', ['org']),
      {
        wrapper: ({ children }: { children: ReactNode }) => (
          <NuqsTestingAdapter
            hasMemory
            searchParams='?section=organizations&org=org-1&location=loc-1'
            onUrlUpdate={(event) => updates.push(event.queryString)}
          >
            {children}
          </NuqsTestingAdapter>
        ),
      }
    );

    act(() => {
      result.current.selectSection('suggest-place');
    });

    await waitFor(() => expect(updates.at(-1) ?? '').toContain('section=suggest-place'));
    expect(updates.at(-1)).toContain('org=org-1');
    expect(updates.at(-1)).not.toContain('location=');

    act(() => {
      result.current.selectSection('feedback');
    });

    await waitFor(() => expect(updates.at(-1) ?? '').toContain('section=feedback'));
    expect(updates.at(-1)).toContain('org=org-1');
    expect(result.current.activeSection).toBe('feedback');
  });
});
