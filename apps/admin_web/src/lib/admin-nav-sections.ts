import type { NavSection } from '@/components/app-shell';

export interface AdminNavGroup {
  /** Heading shown above the group. Omit for a single unlabeled item. */
  label?: string;
  sections: readonly { key: string; label: string }[];
  /** Sort this group's labels A-Z. Workspace order stays as declared. */
  sort?: boolean;
}

/**
 * Build the admin sidebar from labeled groups. Declaration order of
 * groups is kept. `sort` orders labels inside a group.
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
    return sections.map((section) => ({
      ...section,
      group: group.label,
    }));
  });
}
