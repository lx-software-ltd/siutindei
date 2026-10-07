import type { NavSection } from '@/components/app-shell';

export interface AdminNavGroup {
  sections: readonly { key: string; label: string }[];
  /** Sort this group's labels A-Z. Workspace order stays as declared. */
  sort?: boolean;
  /** Horizontal rule before the first item in this group. */
  dividerBefore?: boolean;
}

/**
 * Build the admin sidebar. Declaration order of groups is kept.
 * `sort` orders labels inside a group. `dividerBefore` draws a rule
 * before that group's first item.
 */
export function buildAdminNavSections(
  groups: readonly AdminNavGroup[]
): NavSection[] {
  return groups.flatMap((group) => {
    const sections = group.sort
      ? [...group.sections].sort((left, right) =>
          left.label.localeCompare(right.label, 'en', { sensitivity: 'base' })
        )
      : [...group.sections];
    return sections.map((section, index) => ({
      ...section,
      dividerBefore: Boolean(group.dividerBefore) && index === 0,
    }));
  });
}
