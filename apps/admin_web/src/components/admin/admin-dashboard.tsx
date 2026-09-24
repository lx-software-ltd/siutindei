'use client';

import { useCallback, useEffect, useMemo } from 'react';
import { useQueryState } from 'nuqs';

import { AppShell } from '../app-shell';
import { useAuth } from '../auth-provider';
import { LoginScreen } from '../login-screen';
import { StatusBanner } from '../status-banner';
import {
  OrganizationsPanel,
  LocationsPanel,
  ActivityCategoriesPanel,
  ActivitiesPanel,
  PricingPanel,
  SchedulesPanel,
} from '../shared';
import { ApiKeysPanel } from './api-keys-panel';
import { CategorySuggestionsPanel } from './category-suggestions/category-suggestions-panel';
import { AuditLogsPanel } from './audit-logs-panel';
import { CognitoUsersPanel } from './cognito-users-panel';
import { FeedbackLabelsPanel } from './feedback-labels-panel';
import { FeedbackPanel } from './feedback-panel';
import { ImportsPanel } from './imports-panel';
import { MediaPanel } from './media-panel';
import { ManagerDashboard } from './manager-dashboard';
import { TicketsPanel } from './tickets-panel';
import { UserDashboard } from './user-dashboard';

const sectionLabels = [
  { key: 'organizations', label: 'Organizations' },
  { key: 'media', label: 'Media' },
  { key: 'locations', label: 'Locations' },
  { key: 'activities', label: 'Activities' },
  { key: 'pricing', label: 'Pricing' },
  { key: 'schedules', label: 'Schedules' },
  { key: 'tickets', label: 'Tickets', dividerBefore: true },
  { key: 'feedback', label: 'Feedback' },
  { key: 'feedback-labels', label: 'Feedback Labels' },
  { key: 'cognito-users', label: 'Users' },
  { key: 'activity-categories', label: 'Categories' },
  { key: 'category-suggestions', label: 'Category Suggestions' },
  { key: 'api-keys', label: 'API Keys' },
  { key: 'audit-logs', label: 'Audit Logs' },
  { key: 'imports', label: 'Imports' },
];

export function AdminDashboard() {
  const { status, user, isAdmin, isManager, logout, error } = useAuth();
  const [sectionParam, setSectionParam] = useQueryState('section');
  const isValidSectionParam = useMemo(
    () => sectionLabels.some((section) => section.key === sectionParam),
    [sectionParam]
  );
  const activeSection = useMemo(() => {
    return isValidSectionParam && sectionParam ? sectionParam : 'organizations';
  }, [isValidSectionParam, sectionParam]);

  useEffect(() => {
    if (sectionParam && isValidSectionParam) {
      return;
    }
    void setSectionParam(activeSection, { history: 'replace' });
  }, [activeSection, isValidSectionParam, sectionParam, setSectionParam]);

  const handleSelectSection = useCallback(
    (nextSection: string) => {
      const isValidSection = sectionLabels.some(
        (section) => section.key === nextSection
      );
      if (!isValidSection) {
        return;
      }
      void setSectionParam(nextSection, { history: 'push' });
    },
    [setSectionParam]
  );

  const activeContent = useMemo(() => {
    switch (activeSection) {
      case 'media':
        return <MediaPanel />;
      case 'locations':
        return <LocationsPanel mode='admin' />;
      case 'activity-categories':
        return <ActivityCategoriesPanel />;
      case 'category-suggestions':
        return <CategorySuggestionsPanel />;
      case 'activities':
        return <ActivitiesPanel mode='admin' />;
      case 'pricing':
        return <PricingPanel mode='admin' />;
      case 'schedules':
        return <SchedulesPanel mode='admin' />;
      case 'imports':
        return <ImportsPanel />;
      case 'tickets':
        return <TicketsPanel />;
      case 'feedback':
        return <FeedbackPanel />;
      case 'feedback-labels':
        return <FeedbackLabelsPanel />;
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
        <StatusBanner variant='info' title='Loading'>
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
    return <UserDashboard />;
  }

  // Admin experience (full access)
  return (
    <AppShell
      sections={sectionLabels}
      activeKey={activeSection}
      onSelect={handleSelectSection}
      onLogout={logout}
      userEmail={user?.email}
      lastAuthTime={user?.lastAuthTime}
    >
      {error && (
        <StatusBanner variant='error' title='Session'>
          {error}
        </StatusBanner>
      )}
      {activeContent}
    </AppShell>
  );
}
