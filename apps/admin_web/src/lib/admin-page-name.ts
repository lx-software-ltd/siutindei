/**
 * Tab labels shared by the strip and `formatAdminPageName`.
 * Rename a tab here so the page name stays in step.
 */
export const adminTabLabel = {
  import: 'Import',
  history: 'History',
  settings: 'Settings',
  categories: 'Categories',
  suggestions: 'Suggestions',
  feedback: 'Feedback',
  labels: 'Labels',
  duplicates: 'Duplicates',
  names: 'Names',
  locations: 'Locations',
  translations: 'Translations',
  deleted: 'Deleted',
  runs: 'Runs',
} as const;

/**
 * Admin page name: nav only, or `Nav · Tab` when a tab distinguishes the view.
 * Sub-tabs (Catalog Table / Map) are not passed in.
 */
export function formatAdminPageName(
  nav: string,
  tab?: string | null
): string {
  const section = nav.trim();
  const view = tab?.trim();
  if (!view || tabRepeatsNav(section, view)) {
    return section;
  }
  return `${section} · ${view}`;
}

function stem(word: string): string {
  const value = word.toLowerCase();
  if (value.endsWith('ies') && value.length > 3) {
    return `${value.slice(0, -3)}y`;
  }
  if (value.endsWith('s') && !value.endsWith('ss') && value.length > 1) {
    return value.slice(0, -1);
  }
  return value;
}

function tabRepeatsNav(nav: string, tab: string): boolean {
  return stem(nav) === stem(tab);
}
