/** Sections that edit one organization. `org` stays set while moving among them. */
export const WORKSPACE_SECTIONS = [
  'organizations',
  'media',
  'locations',
  'activities',
  'pricing',
  'schedules',
] as const;

export type WorkspaceSection = (typeof WORKSPACE_SECTIONS)[number];

export function isWorkspaceSection(section: string | null | undefined): boolean {
  return WORKSPACE_SECTIONS.some((item) => item === section);
}
