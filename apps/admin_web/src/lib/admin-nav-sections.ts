import type { NavSection } from '@/components/app-shell';

/**
 * Build the admin sidebar: keep the primary CRUD group in declaration
 * order, then append tool pages sorted A-Z. The divider always sits
 * before the first tool item.
 *
 * Add future second-group pages to `tools` only. Do not insert them
 * into `primary`, and do not set `dividerBefore` by hand.
 */
export function buildAdminNavSections(
  primary: readonly NavSection[],
  tools: readonly NavSection[]
): NavSection[] {
  const sortedTools = [...tools]
    .map(({ dividerBefore: _ignored, ...section }) => section)
    .sort((left, right) =>
      left.label.localeCompare(right.label, 'en', { sensitivity: 'base' })
    );

  if (sortedTools.length === 0) {
    return primary.map(({ dividerBefore: _divider, ...section }) => section);
  }

  return [
    ...primary.map(({ dividerBefore: _divider, ...section }) => section),
    { ...sortedTools[0], dividerBefore: true },
    ...sortedTools.slice(1),
  ];
}
