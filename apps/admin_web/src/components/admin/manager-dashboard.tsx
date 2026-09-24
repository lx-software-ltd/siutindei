'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  ApiError,
} from '../../lib/api-client';
import { listManagerOrganizations } from '../../lib/api-client-manager';
import {
  getUserAccessStatus,
  getUserFeedback,
  getUserSuggestions,
  type ManagerStatusResponse,
  type Ticket,
} from '../../lib/api-client-user';
import { useAdminSectionQuery } from '@/hooks/use-admin-section-query';
import { usePrefetchAdminSection } from '@/hooks/use-prefetch-admin-section';

import { useAuth } from '../auth-provider';
import { AppShell } from '../app-shell';
import { StatusBanner } from '../status-banner';
import {
  OrganizationsPanel,
  LocationsPanel,
  ActivitiesPanel,
  PricingPanel,
  SchedulesPanel,
} from '../shared';
import { AccessRequestForm } from './access-request-form';
import { FeedbackForm } from './feedback-form';
import { PendingRequestNotice } from './pending-request-notice';
import { MediaPanel } from './media-panel';
import { PendingFeedbackNotice } from './pending-feedback-notice';
import { SuggestionForm } from './suggestion-form';
import { PendingSuggestionNotice } from './pending-suggestion-notice';

type ManagerView = 'loading' | 'request-form' | 'pending' | 'dashboard';

const managerSectionLabels = [
  { key: 'organizations', label: 'Organizations' },
  { key: 'media', label: 'Media' },
  { key: 'locations', label: 'Locations' },
  { key: 'activities', label: 'Activities' },
  { key: 'pricing', label: 'Pricing' },
  { key: 'schedules', label: 'Schedules' },
  { key: 'suggest-place', label: 'Suggest a Place', dividerBefore: true },
  { key: 'feedback', label: 'Feedback' },
];

export function ManagerDashboard() {
  const { user, logout, error: authError } = useAuth();
  const prefetchSection = usePrefetchAdminSection('manager');
  const [managerStatus, setManagerStatus] = useState<ManagerStatusResponse | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState<ManagerView>('loading');
  const [pendingRequest, setPendingRequest] = useState<Ticket | null>(null);
  const [pendingSuggestion, setPendingSuggestion] =
    useState<Ticket | null>(null);
  const [pendingFeedback, setPendingFeedback] = useState<Ticket | null>(null);
  const [managerOrgName, setManagerOrgName] = useState<string | null>(null);
  const { activeSection, selectSection } = useAdminSectionQuery(
    managerSectionLabels,
    'organizations'
  );

  const loadManagerOrgName = useCallback(async (): Promise<string | null> => {
    try {
      const response = await listManagerOrganizations();
      const name = response.items[0]?.name?.trim();
      return name ? name : null;
    } catch {
      return null;
    }
  }, []);

  const loadManagerStatus = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      // Load access request, suggestions, and feedback in parallel
      const [status, suggestionsStatus, feedbackStatus] = await Promise.all([
        getUserAccessStatus(),
        getUserSuggestions(),
        getUserFeedback(),
      ]);
      setManagerStatus(status);

      // Check for pending suggestion
      if (suggestionsStatus.has_pending_suggestion) {
        const pending = suggestionsStatus.suggestions.find(
          (s) => s.status === 'pending'
        );
        if (pending) {
          setPendingSuggestion(pending);
        }
      }

      if (feedbackStatus.has_pending_feedback) {
        const pending = feedbackStatus.feedbacks.find(
          (item) => item.status === 'pending'
        );
        if (pending) {
          setPendingFeedback(pending);
        }
      }

      if (status.organizations_count > 0) {
        // User has organizations, show the dashboard
        const orgName = await loadManagerOrgName();
        setManagerOrgName(orgName);
        setView('dashboard');
      } else if (status.has_pending_request && status.pending_request) {
        // User has a pending request
        setManagerOrgName(null);
        setPendingRequest(status.pending_request);
        setView('pending');
      } else {
        // User has no organizations and no pending request
        setManagerOrgName(null);
        setView('request-form');
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to load your account status.';
      setError(message);
      setView('request-form');
    } finally {
      setIsLoading(false);
    }
  }, [loadManagerOrgName]);

  useEffect(() => {
    loadManagerStatus();
  }, [loadManagerStatus]);

  const handleRequestSubmitted = (request: Ticket) => {
    setPendingRequest(request);
    setView('pending');
  };

  const handleSuggestionSubmitted = (suggestion: Ticket) => {
    setPendingSuggestion(suggestion);
  };

  const handleFeedbackSubmitted = (feedback: Ticket) => {
    setPendingFeedback(feedback);
  };

  const headerDescription = managerOrgName
    ? `Manage your organization, ${managerOrgName}.`
    : 'Manage your organization.';

  // Use shared components with mode='manager'
  const activeContent = useMemo(() => {
    switch (activeSection) {
      case 'media':
        return <MediaPanel mode='manager' />;
      case 'locations':
        return <LocationsPanel mode='manager' />;
      case 'activities':
        return <ActivitiesPanel mode='manager' />;
      case 'pricing':
        return <PricingPanel mode='manager' />;
      case 'schedules':
        return <SchedulesPanel mode='manager' />;
      case 'suggest-place':
        if (pendingSuggestion) {
          return <PendingSuggestionNotice suggestion={pendingSuggestion} />;
        }
        return <SuggestionForm onSuggestionSubmitted={handleSuggestionSubmitted} />;
      case 'feedback':
        if (pendingFeedback) {
          return <PendingFeedbackNotice feedback={pendingFeedback} />;
        }
        return <FeedbackForm onFeedbackSubmitted={handleFeedbackSubmitted} />;
      case 'organizations':
      default:
        return <OrganizationsPanel mode='manager' />;
    }
  }, [activeSection, pendingFeedback, pendingSuggestion]);

  // Loading state
  if (view === 'loading' || isLoading) {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <StatusBanner variant='info' title='Loading'>
          Loading your account information...
        </StatusBanner>
      </main>
    );
  }

  // Error state with request form fallback
  if (error && view === 'request-form') {
    return (
      <AppShell
        sections={[]}
        activeKey=''
        onSelect={() => {}}
        onLogout={logout}
        userEmail={user?.email}
        lastAuthTime={user?.lastAuthTime}
        headerDescription={headerDescription}
      >
        <StatusBanner variant='error' title='Error'>
          {error}
        </StatusBanner>
        <div className='mt-6'>
          <AccessRequestForm onRequestSubmitted={handleRequestSubmitted} />
        </div>
      </AppShell>
    );
  }

  // Pending request view
  if (view === 'pending' && pendingRequest) {
    return (
      <AppShell
        sections={[]}
        activeKey=''
        onSelect={() => {}}
        onLogout={logout}
        userEmail={user?.email}
        lastAuthTime={user?.lastAuthTime}
        headerDescription={headerDescription}
      >
        {authError && (
          <StatusBanner variant='error' title='Session'>
            {authError}
          </StatusBanner>
        )}
        <PendingRequestNotice request={pendingRequest} />
      </AppShell>
    );
  }

  // Request form view (no organizations, no pending request)
  if (view === 'request-form') {
    return (
      <AppShell
        sections={[]}
        activeKey=''
        onSelect={() => {}}
        onLogout={logout}
        userEmail={user?.email}
        lastAuthTime={user?.lastAuthTime}
        headerDescription={headerDescription}
      >
        {authError && (
          <StatusBanner variant='error' title='Session'>
            {authError}
          </StatusBanner>
        )}
        <AccessRequestForm onRequestSubmitted={handleRequestSubmitted} />
      </AppShell>
    );
  }

  // Dashboard view (manager has organizations)
  return (
    <AppShell
      sections={managerSectionLabels}
      activeKey={activeSection}
      onSelect={selectSection}
      onIntent={prefetchSection}
      onLogout={logout}
      userEmail={user?.email}
      lastAuthTime={user?.lastAuthTime}
      headerDescription={headerDescription}
    >
      {authError && (
        <StatusBanner variant='error' title='Session'>
          {authError}
        </StatusBanner>
      )}
      <div>{activeContent}</div>
    </AppShell>
  );
}
