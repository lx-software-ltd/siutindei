'use client';

import { useCallback } from 'react';
import { parseAsString, useQueryStates } from 'nuqs';

import { isWorkspaceSection } from '@/lib/organization-scope';

/**
 * The organization the workspace is editing. `new` is a draft.
 * Catalog and tool sections clear this when the operator leaves the workspace.
 */
export function useOrganizationScope() {
  const [query, setQuery] = useQueryStates({
    section: parseAsString,
    org: parseAsString,
    organization: parseAsString,
    edit: parseAsString,
  });

  const orgParam = query.org;
  const orgId = orgParam && orgParam !== 'new' ? orgParam : null;
  const isDraft = orgParam === 'new';

  const setOrg = useCallback(
    (next: string | null) => {
      void setQuery({ org: next });
    },
    [setQuery]
  );

  const openWorkspace = useCallback(
    (nextOrg: string, section = 'organizations') => {
      void setQuery({
        section,
        org: nextOrg,
        organization: null,
        edit: null,
      });
    },
    [setQuery]
  );

  const openCatalog = useCallback(() => {
    void setQuery({ section: 'catalog', org: null });
  }, [setQuery]);

  return {
    section: query.section,
    orgParam,
    orgId,
    isDraft,
    isWorkspace: isWorkspaceSection(query.section),
    legacyOrgId: query.organization || query.edit || null,
    setOrg,
    openWorkspace,
    openCatalog,
  };
}
