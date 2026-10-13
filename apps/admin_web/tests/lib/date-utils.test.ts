import { describe, expect, it } from 'vitest';

import { formatDate, formatDateTime } from '@/lib/date-utils';

describe('formatDate', () => {
  it('prints month and day only', () => {
    const local = new Date(2026, 9, 13, 14, 36);
    expect(formatDate(local.toISOString())).toBe('Oct 13');
  });

  it('returns an em dash for empty or invalid values', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate('not-a-date')).toBe('—');
  });
});

describe('formatDateTime', () => {
  it('prints month, day, and zero-padded 12-hour time', () => {
    const afternoon = new Date(2026, 9, 13, 14, 36);
    expect(formatDateTime(afternoon.toISOString())).toBe('Oct 13, 02:36 PM');
    const morning = new Date(2026, 9, 13, 2, 5);
    expect(formatDateTime(morning.toISOString())).toBe('Oct 13, 02:05 AM');
    const noon = new Date(2026, 9, 13, 12, 0);
    expect(formatDateTime(noon.toISOString())).toBe('Oct 13, 12:00 PM');
    const midnight = new Date(2026, 9, 13, 0, 0);
    expect(formatDateTime(midnight.toISOString())).toBe('Oct 13, 12:00 AM');
  });
});
