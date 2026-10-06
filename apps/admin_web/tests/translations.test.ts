import { describe, expect, it } from 'vitest';

import {
  buildTranslationsPayload,
  mergePreservedTranslations,
} from '../src/lib/translations';

describe('mergePreservedTranslations', () => {
  it('keeps zh-HK when the form only edits zh and yue', () => {
    const payload = buildTranslationsPayload({
      zh: '陶藝',
      yue: '',
    });
    const merged = mergePreservedTranslations(payload, {
      zh: '舊',
      yue: '舊粵',
      'zh-HK': '陶藝',
    });
    expect(merged).toEqual({
      zh: '陶藝',
      'zh-HK': '陶藝',
    });
  });
});
