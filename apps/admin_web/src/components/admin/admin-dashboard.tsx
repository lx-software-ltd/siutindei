'use client';

import { useMemo } from 'react';

import { useAdminSectionQuery } from '@/hooks/use-admin-section-query';
import { useOrganizationScope } from '@/hooks/use-organization-scope';
import { usePrefetchAdminSection } from '@/hooks/use-prefetch-admin-section';
import { buildAdminNavSections } from '@/lib/admin-nav-sections';

import { AppShell } from '../app-shell';
import { useAuth } from '../auth-provider';
import { LoginScreen } from '../login-screen';
import { StatusBanner } from '../status-banner';
import {
  OrganizationsPanel,
  LocationsPanel,
  ActivitiesPanel,
  PricingPanel,
  SchedulesPanel,
} from '../shared';
import { ApiKeysPanel } from './api-keys-panel';
import { AuditLogsPanel } from './audit-logs-panel';
import { CategoriesPage } from './categories-page';
import { CognitoUsersPanel } from './cognito-users-panel';
import { FeedbackPage } from './feedback-page';
import { DataQualityPage } from './data-quality/data-quality-page';
import { ImportsPanel } from './imports-panel';
import { CatalogPanel } from './org-review/review-queue-panel';
import { MediaPanel } from './media-panel';
import { ManagerDashboard } from './manager-dashboard';
import { TicketsPanel } from './tickets-panel';
import { AccountHome } from './user-dashboard';

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
      { key: 'api-keys', label: 'API Keys' },
      { key: 'cognito-users', label: 'Users' },
    ],
  },
  {
    sections: [{ key: 'audit-logs', label: 'Audit Logs' }],
  },
]);

const recognizedSections = [
  ...sectionLabels,
  { key: 'category-suggestions', label: 'Category Suggestions' },
  { key: 'feedback-labels', label: 'Feedback Labels' },
];

export function AdminDashboard() {
  const { status, user, isAdmin, isManager, logout, error } = useAuth();
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

  if (status === 'loading') {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <StatusBanner variant='info' kind='info'>
          Preparing your admin session.
        </StatusBanner>
      </main>
    );
  }

  if (status === 'unauthenticated') {
    return <LoginScreen />;
  }

  // If user is in the manager group but NOT in the admin group,
  // show the manager-specific experience
  if (isManager && !isAdmin) {
    return <ManagerDashboard />;
  }

  // If user is neither admin nor manager, show the user dashboard
  // where they can request to become a manager
  if (!isAdmin && !isManager) {
    return <AccountHome />;
  }

  // Admin experience (full access)
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
        <StatusBanner variant='error' kind='error'>
          {error}
        </StatusBanner>
      )}
      {activeContent}
    </AppShell>
  );
}
