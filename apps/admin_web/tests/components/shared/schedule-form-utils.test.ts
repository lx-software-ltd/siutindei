import { describe, expect, it } from 'vitest';

import {
  getLanguageOption,
  scheduleLanguageMarks,
  toLanguageCodes,
} from '@/components/shared/schedules/schedule-form-utils';

describe('schedule language marks', () => {
  it('shows zh-HK with the Cantonese flag and keeps it in the editor', () => {
    expect(toLanguageCodes(['zh-HK', 'zh_HK', 'yue', 'en'])).toEqual([
      'yue',
      'en',
    ]);
    expect(getLanguageOption('zh-HK')?.flagSrc).toBe('/flags/hk.png');
    expect(scheduleLanguageMarks(['zh-HK', 'yue', 'ja'])).toEqual([
      {
        kind: 'flag',
        code: 'yue',
        label: 'Cantonese (yue)',
        flagSrc: '/flags/hk.png',
      },
      { kind: 'text', code: 'ja' },
    ]);
  });
});
