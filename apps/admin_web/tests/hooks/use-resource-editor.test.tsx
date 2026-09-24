import { act, renderHook, waitFor } from '@testing-library/react';
import { NuqsTestingAdapter } from 'nuqs/adapters/testing';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useResourceEditor } from '@/hooks/use-resource-editor';
import { ApiError } from '@/lib/api-client-core';

const api = {
  list: vi.fn(async () => ({ items: [{ id: 'a', name: 'A' }], next_cursor: null })),
  get: vi.fn(async (id: string) => ({ id, name: 'Fetched' })),
  create: vi.fn(async (payload: unknown) => ({ id: 'new-1', ...(payload as object) })),
  update: vi.fn(),
  delete: vi.fn(async () => undefined),
};

vi.mock('@/lib/resource-api', () => ({
  getResourceApi: () => api,
}));

vi.mock('@/hooks/use-confirm-dialog', () => ({
  useConfirmDialog: () => ({ confirm: async () => true, confirmDialog: null }),
}));

function wrapper(searchParams = '') {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <NuqsTestingAdapter searchParams={searchParams}>{children}</NuqsTestingAdapter>;
  };
}

function renderEditor(searchParams = '') {
  return renderHook(
    () =>
      useResourceEditor<{ id: string; name: string }, { name: string }>({
        resource: 'organizations',
        mode: 'admin',
        emptyForm: { name: '' },
        itemToForm: (item) => ({ name: item.name }),
        paramName: 'organization',
        noun: 'organization',
      }),
    { wrapper: wrapper(searchParams) }
  );
}

describe('useResourceEditor', () => {
  beforeEach(() => {
    api.list.mockReset();
    api.list.mockResolvedValue({ items: [{ id: 'a', name: 'A' }], next_cursor: null });
    api.get.mockReset();
    api.create.mockReset();
    api.create.mockImplementation(async (payload: unknown) => ({
      id: 'new-1',
      ...(payload as object),
    }));
    api.update.mockReset();
    api.delete.mockReset();
    api.delete.mockResolvedValue(undefined);
  });

  it('drops a record created and then deleted in the same session', async () => {
    api.list.mockResolvedValue({ items: [{ id: 'a', name: 'A' }], next_cursor: null });
    const { result } = renderEditor();
    await waitFor(() => expect(result.current.items.map((item) => item.id)).toEqual(['a']));

    await act(async () => {
      await result.current.handleSubmit((form) => form);
    });
    await waitFor(() => expect(result.current.items.map((item) => item.id)).toEqual(['new-1', 'a']));

    await act(async () => {
      await result.current.handleDelete({ id: 'new-1', name: 'Created' });
    });

    expect(api.delete).toHaveBeenCalledWith('new-1');
    expect(result.current.items.map((item) => item.id)).toEqual(['a']);
  });

  it('fetches a deep-linked record that is not on the loaded page', async () => {
    api.list.mockResolvedValue({ items: [{ id: 'a', name: 'A' }], next_cursor: null });
    api.get.mockResolvedValue({ id: 'deep', name: 'Fetched' });
    const { result } = renderEditor('?organization=deep');

    await waitFor(() => expect(result.current.items.map((item) => item.id)).toContain('deep'));
    expect(api.get).toHaveBeenCalledWith('deep');
    expect(result.current.listError).toBe('');
  });

  it('explains when a deep-linked record cannot be loaded', async () => {
    api.list.mockResolvedValue({ items: [{ id: 'a', name: 'A' }], next_cursor: null });
    api.get.mockRejectedValue(new ApiError('missing', 404));
    const { result } = renderEditor('?organization=missing');

    await waitFor(() =>
      expect(result.current.listError).toBe(
        'That record could not be opened. It may have been deleted.'
      )
    );
    expect(result.current.items.map((item) => item.id)).toEqual(['a']);
  });
});
