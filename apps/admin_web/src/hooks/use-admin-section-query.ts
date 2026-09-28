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
  ticket: parseAsString,
  user: parseAsString,
  'audit-log': parseAsString,
  review: parseAsString,
  job: parseAsString,
  'import-job': parseAsString,
};

interface SectionLabel {
  key: string;
}

/**
 * Dashboard section plus the record params that belong to it. Choosing a
 * section drops params from other sections so they do not pile up in the URL.
 */
export function useAdminSectionQuery(sections: readonly SectionLabel[], fallback: string) {
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
    const stale = staleRecordParams(activeSection, current);
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
  }, [activeSection, isValidSection, query, sectionParam, setQuery]);

  const selectSection = useCallback(
    (nextSection: string) => {
      if (!sections.some((section) => section.key === nextSection)) {
        return;
      }
      void setQuery(patchForSectionChange(nextSection), { history: 'push' });
    },
    [sections, setQuery]
  );

  return { activeSection, selectSection };
}
