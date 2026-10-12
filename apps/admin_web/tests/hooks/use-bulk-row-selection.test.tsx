import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useBulkRowSelection } from '@/hooks/use-bulk-row-selection';

describe('useBulkRowSelection', () => {
  const items = [{ id: 'a' }, { id: 'b' }];

  it('ticks only the chosen row', () => {
    const { result } = renderHook(() => useBulkRowSelection(items, true));

    act(() => {
      result.current.toggleRow('a', true);
    });

    expect(result.current.selected.has('a')).toBe(true);
    expect(result.current.selected.has('b')).toBe(false);
    expect(result.current.selectScope).toBe('some');
    expect(result.current.headerChecked).toBe(false);
  });

  it('does not re-select every visible row after a single tick', () => {
    const { result, rerender } = renderHook(
      ({ rows }) => useBulkRowSelection(rows, true),
      { initialProps: { rows: items } }
    );

    act(() => {
      result.current.toggleRow('a', true);
    });
    rerender({ rows: items });

    expect([...result.current.selected]).toEqual(['a']);
    expect(result.current.selectScope).toBe('some');
  });

  it('drops out of visible scope when a row is unchecked', () => {
    const { result } = renderHook(() => useBulkRowSelection(items, true));

    act(() => {
      result.current.cycleHeader();
    });
    expect(result.current.selectScope).toBe('visible');
    expect(result.current.selected.size).toBe(2);

    act(() => {
      result.current.toggleRow('b', false);
    });

    expect(result.current.selectScope).toBe('some');
    expect([...result.current.selected]).toEqual(['a']);
    expect(result.current.headerChecked).toBe(false);
  });

  it('cycles the header from visible rows to all matching rows', () => {
    const { result } = renderHook(() => useBulkRowSelection(items, true));

    act(() => {
      result.current.cycleHeader();
    });
    expect(result.current.selectScope).toBe('visible');
    expect(result.current.headerLabel).toBe('Select all matching rows');

    act(() => {
      result.current.cycleHeader();
    });
    expect(result.current.selectScope).toBe('all');
    expect(result.current.headerChecked).toBe(true);
    expect(result.current.headerLabel).toBe('Clear selection');
  });
});
