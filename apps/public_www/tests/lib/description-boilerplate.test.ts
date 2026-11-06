import { describe, expect, it } from 'vitest';

import {
  descriptionIsImportBoilerplate,
  hideImportTemplateCopy,
} from '@/lib/activities/description-boilerplate';

describe('import description filler', () => {
  it('detects EDB and LCSD sentences and keeps unique copy', () => {
    expect(
      descriptionIsImportBoilerplate(
        'Harbour Club is a class or early-years centre in CENTRAL for children and families.',
      ),
    ).toBe(true);
    expect(
      descriptionIsImportBoilerplate(
        'Harbour Park is a public outdoor venue in Tai Po for children and families.',
      ),
    ).toBe(true);
    expect(
      descriptionIsImportBoilerplate('南區嘅幼兒或興趣班，適合小朋友同家庭。'),
    ).toBe(true);
    expect(
      descriptionIsImportBoilerplate(
        'Saturday art class for children and families in the harbour.',
      ),
    ).toBe(false);
  });

  it('hides blank or filler template copy only', () => {
    expect(hideImportTemplateCopy('template', '')).toBe(true);
    expect(
      hideImportTemplateCopy(
        'template',
        'Harbour Park is a sports venue in Southern for children and families.',
      ),
    ).toBe(true);
    expect(
      hideImportTemplateCopy(
        'template',
        'Saturday art class for children in the harbour.',
      ),
    ).toBe(false);
    expect(
      hideImportTemplateCopy(
        'official',
        'Harbour Club is a class or early-years centre in CENTRAL for children and families.',
      ),
    ).toBe(false);
  });
});
