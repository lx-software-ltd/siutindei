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

function tabRepeatsNav(nav: string, tab: string): boolean {
  const section = nav.toLowerCase();
  const view = tab.toLowerCase();
  return section === view || section === `${view}s` || view === `${section}s`;
}
