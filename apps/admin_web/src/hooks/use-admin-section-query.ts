'use client';

import { useCallback, useEffect, useRef } from 'react';
import { parseAsString, useQueryStates } from 'nuqs';

import {
  ADMIN_RECORD_PARAMS,
  patchForSectionChange,
  staleRecordParams,
  type AdminRecordParam,
} from '@/lib/admin-section-params';

const parsers = {
  section: parseAsString,
  edit: parseAsString,
  org: parseAsString,
  organization: parseAsString,
  location: parseAsString,
  activity: parseAsString,
  pricing: parseAsString,
  schedule: parseAsString,
  category: parseAsString,
  feedback: parseAsString,
  'feedback-label': parseAsString,
  'api-key': parseAsString,
  suggestion: parseAsString,
  'category-check': parseAsString,
  ticket: parseAsString,
  user: parseAsString,
  'audit-log': parseAsString,
  review: parseAsString,
  job: parseAsString,
  'import-job': parseAsString,
  duplicate: parseAsString,
  'name-fix': parseAsString,
  'location-fix': parseAsString,
  'translation-fix': parseAsString,
};

interface SectionLabel {
  key: string;
}

const NO_PRESERVED_PARAMS: readonly AdminRecordParam[] = [];

/**
 * Dashboard section plus the record params that belong to it. Choosing a
 * section drops params from other sections so they do not pile up in the URL.
 * `preserve` is for params every section of this console keeps, such as the
 * manager organization id.
 */
export function useAdminSectionQuery(
  sections: readonly SectionLabel[],
  fallback: string,
  preserve: readonly AdminRecordParam[] = NO_PRESERVED_PARAMS
) {
  const [query, setQuery] = useQueryStates(parsers);
  const sectionParam = query.section;
  const isValidSection = sections.some((section) => section.key === sectionParam);
  const activeSection = isValidSection && sectionParam ? sectionParam : fallback;
  const appliedStale = useRef('');

  useEffect(() => {
    if (!sectionParam || !isValidSection) {
      void setQuery({ section: activeSection }, { history: 'replace' });
      return;
    }
    const current: Partial<Record<AdminRecordParam, string | null>> = {};
    for (const key of ADMIN_RECORD_PARAMS) {
      current[key] = query[key] ?? null;
    }
    const stale = staleRecordParams(activeSection, current, preserve);
    const staleKey = Object.keys(stale).sort().join(',');
    if (!staleKey) {
      appliedStale.current = '';
      return;
    }
    if (appliedStale.current === staleKey) {
      return;
    }
    appliedStale.current = staleKey;
    void setQuery(stale, { history: 'replace' });
  }, [activeSection, isValidSection, preserve, query, sectionParam, setQuery]);

  const selectSection = useCallback(
    (nextSection: string) => {
      if (!sections.some((section) => section.key === nextSection)) {
        return;
      }
      void setQuery(patchForSectionChange(nextSection, preserve), {
        history: 'push',
      });
    },
    [preserve, sections, setQuery]
  );

  return { activeSection, selectSection };
}
