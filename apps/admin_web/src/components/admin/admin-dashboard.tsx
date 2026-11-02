'use client';

import { useMemo } from 'react';

import { useAdminSectionQuery } from '@/hooks/use-admin-section-query';
import { useOrganizationScope } from '@/hooks/use-organization-scope';
import { usePrefetchAdminSection } from '@/hooks/use-prefetch-admin-section';
import { buildAdminNavSections } from '@/lib/admin-nav-sections';
import { adminTabLabel } from '@/lib/admin-page-name';

import { AppShell } from '../app-shell';
import { useAuth } from '../auth-provider';
import { LoginBackdrop } from '../login/login-backdrop';
import { LoginBrandHeader } from '../login/login-brand-header';
import { LoginLoadingNotice } from '../login/login-loading-notice';
import { LoginScreen } from '../login-screen';
import { StatusBanner } from '../status-banner';
import { loadDashboardSection } from './dashboard-section';

const MediaPanel = loadDashboardSection(() =>
  import('./media-panel').then((mod) => mod.MediaPanel)
);
const LocationsPanel = loadDashboardSection(() =>
  import('../shared/locations-panel').then((mod) => mod.LocationsPanel)
);
const CategoriesPage = loadDashboardSection(() =>
  import('./categories-page').then((mod) => mod.CategoriesPage)
);
const ActivitiesPanel = loadDashboardSection(() =>
  import('../shared/activities-panel').then((mod) => mod.ActivitiesPanel)
);
const PricingPanel = loadDashboardSection(() =>
  import('../shared/pricing-panel').then((mod) => mod.PricingPanel)
);
const SchedulesPanel = loadDashboardSection(() =>
  import('../shared/schedules-panel').then((mod) => mod.SchedulesPanel)
);
const ImportsPanel = loadDashboardSection(() =>
  import('./imports-panel').then((mod) => mod.ImportsPanel)
);
const CatalogPanel = loadDashboardSection(() =>
  import('./org-review/review-queue-panel').then((mod) => mod.CatalogPanel)
);
const DataQualityPage = loadDashboardSection(() =>
  import('./data-quality/data-quality-page').then((mod) => mod.DataQualityPage)
);
const TicketsPanel = loadDashboardSection(() =>
  import('./tickets-panel').then((mod) => mod.TicketsPanel)
);
const FeedbackPage = loadDashboardSection(() =>
  import('./feedback-page').then((mod) => mod.FeedbackPage)
);
const CognitoUsersPanel = loadDashboardSection(() =>
  import('./cognito-users-panel').then((mod) => mod.CognitoUsersPanel)
);
const ApiKeysPanel = loadDashboardSection(() =>
  import('./api-keys-panel').then((mod) => mod.ApiKeysPanel)
);
const AuditLogsPanel = loadDashboardSection(() =>
  import('./audit-logs-panel').then((mod) => mod.AuditLogsPanel)
);
const OrganizationsPanel = loadDashboardSection(() =>
  import('../shared/organizations-panel').then((mod) => mod.OrganizationsPanel)
);
const ManagerDashboard = loadDashboardSection(() =>
  import('./manager-dashboard').then((mod) => mod.ManagerDashboard)
);
const AccountHome = loadDashboardSection(() =>
  import('./user-dashboard').then((mod) => mod.AccountHome)
);

const sectionLabels = buildAdminNavSections([
  { sections: [{ key: 'catalog', label: 'Catalog' }] },
  {
    dividerBefore: true,
    sections: [
      { key: 'organizations', label: 'Organization' },
      { key: 'media', label: 'Media' },
      { key: 'locations', label: 'Locations' },
      { key: 'activities', label: 'Activities' },
      { key: 'pricing', label: 'Pricing' },
      { key: 'schedules', label: 'Schedules' },
    ],
  },
  {
    dividerBefore: true,
    sort: true,
    sections: [
      { key: 'imports', label: 'Imports' },
      { key: 'tickets', label: 'Tickets' },
    ],
  },
  {
    sections: [{ key: 'data-quality', label: 'Data quality' }],
  },
  {
    sections: [{ key: 'activity-categories', label: 'Categories' }],
  },
  {
    sections: [{ key: 'feedback', label: 'Feedback' }],
  },
  {
    sort: true,
    sections: [
      { key: 'api-keys', label: 'API keys' },
      { key: 'cognito-users', label: 'Users' },
    ],
  },
  {
    sections: [{ key: 'audit-logs', label: 'Audit logs' }],
  },
]);

const recognizedSections = [
  ...sectionLabels,
  { key: 'category-suggestions', label: adminTabLabel.suggestions },
  { key: 'feedback-labels', label: adminTabLabel.labels },
];

export function AdminDashboard() {
  const { status, isAdmin, isManager } = useAuth();

  if (status === 'loading') {
    return (
      <LoginBackdrop>
        <LoginBrandHeader />
        <LoginLoadingNotice />
      </LoginBackdrop>
    );
  }

  if (status === 'unauthenticated') {
    return <LoginScreen />;
  }

  // The admin section query rewrites unknown sections and drops `org`.
  // It must not stay mounted for a manager: Suggest a Place is unknown
  // here, and Feedback then fights the manager console over `org`.
  if (isManager && !isAdmin) {
    return <ManagerDashboard />;
  }

  if (!isAdmin && !isManager) {
    return <AccountHome />;
  }

  return <AdminConsole />;
}

function AdminConsole() {
  const { user, logout, error } = useAuth();
  const { orgId } = useOrganizationScope();
  const prefetchSection = usePrefetchAdminSection('admin', orgId);
  const { activeSection, selectSection } = useAdminSectionQuery(
    recognizedSections,
    'catalog'
  );

  const activeContent = useMemo(() => {
    switch (activeSection) {
      case 'media':
        return <MediaPanel />;
      case 'locations':
        return <LocationsPanel mode='admin' />;
      case 'activity-categories':
      case 'category-suggestions':
        return <CategoriesPage />;
      case 'activities':
        return <ActivitiesPanel mode='admin' />;
      case 'pricing':
        return <PricingPanel mode='admin' />;
      case 'schedules':
        return <SchedulesPanel mode='admin' />;
      case 'imports':
        return <ImportsPanel />;
      case 'catalog':
        return <CatalogPanel />;
      case 'data-quality':
        return <DataQualityPage />;
      case 'tickets':
        return <TicketsPanel />;
      case 'feedback':
      case 'feedback-labels':
        return <FeedbackPage />;
      case 'cognito-users':
        return <CognitoUsersPanel />;
      case 'api-keys':
        return <ApiKeysPanel />;
      case 'audit-logs':
        return <AuditLogsPanel />;
      case 'organizations':
      default:
        return <OrganizationsPanel mode='admin' />;
    }
  }, [activeSection]);

  return (
    <AppShell
      sections={sectionLabels}
      activeKey={
        activeSection === 'category-suggestions'
          ? 'activity-categories'
          : activeSection === 'feedback-labels'
            ? 'feedback'
            : activeSection
      }
      onSelect={selectSection}
      onIntent={prefetchSection}
      onLogout={logout}
      userEmail={user?.email}
      lastAuthTime={user?.lastAuthTime}
    >
      {error && (
        <StatusBanner kind='error'>
          {error}
        </StatusBanner>
      )}
      {activeContent}
    </AppShell>
  );
}
