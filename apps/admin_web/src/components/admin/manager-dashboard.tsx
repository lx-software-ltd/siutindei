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
  type Ticket,
} from '../../lib/api-client-user';
import { useAdminSectionQuery } from '@/hooks/use-admin-section-query';
import { useOrganizationScope } from '@/hooks/use-organization-scope';
import { usePrefetchAdminSection } from '@/hooks/use-prefetch-admin-section';

import type { Organization } from '../../types/admin';
import { useAuth } from '../auth-provider';
import { AppShell } from '../app-shell';
import { StatusBanner } from '../status-banner';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { Select } from '../ui/select';
import {
  OrganizationsPanel,
  LocationsPanel,
  ActivitiesPanel,
  PricingPanel,
  SchedulesPanel,
} from '../shared';
import { AccountHome } from './user-dashboard';
import { FeedbackForm } from './feedback-form';
import { MediaPanel } from './media-panel';
import { PendingFeedbackNotice } from './pending-feedback-notice';
import { SuggestionForm } from './suggestion-form';
import { PendingSuggestionNotice } from './pending-suggestion-notice';

type ManagerView = 'loading' | 'request-form' | 'pending' | 'dashboard' | 'error';

const managerSectionLabels = [
  { key: 'organizations', label: 'Organization' },
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
  const scope = useOrganizationScope();
  const { orgParam, setOrg } = scope;
  const prefetchSection = usePrefetchAdminSection('manager', scope.orgId);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState<ManagerView>('loading');
  const [managerOrgs, setManagerOrgs] = useState<Organization[]>([]);
  const [pendingSuggestion, setPendingSuggestion] =
    useState<Ticket | null>(null);
  const [pendingFeedback, setPendingFeedback] = useState<Ticket | null>(null);
  const [managerOrgName, setManagerOrgName] = useState<string | null>(null);
  const { activeSection, selectSection } = useAdminSectionQuery(
    managerSectionLabels,
    'organizations'
  );

  const loadManagerOrgs = useCallback(async (): Promise<Organization[]> => {
    const response = await listManagerOrganizations<Organization>();
    return response.items;
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
        const items = await loadManagerOrgs();
        setManagerOrgs(items);
        if (items.length === 0) {
          setManagerOrgName(null);
          setError('No organization is assigned to this account.');
          setView('error');
          return;
        }
        const orgName = items[0]?.name?.trim();
        setManagerOrgName(orgName ? orgName : null);
        const current =
          orgParam !== null && items.some((org) => org.id === orgParam);
        if (!current) {
          setOrg(items[0].id);
        }
        setView('dashboard');
      } else {
        setManagerOrgs([]);
        setManagerOrgName(null);
        setView('request-form');
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to load your account status.';
      setError(message);
      setView('error');
    } finally {
      setIsLoading(false);
    }
  }, [loadManagerOrgs, orgParam, setOrg]);

  useEffect(() => {
    loadManagerStatus();
  }, [loadManagerStatus]);

  useEffect(() => {
    if (view !== 'dashboard' || orgParam || managerOrgs.length === 0) {
      return;
    }
    setOrg(managerOrgs[0].id);
  }, [managerOrgs, orgParam, setOrg, view]);

  const handleSuggestionSubmitted = (suggestion: Ticket) => {
    setPendingSuggestion(suggestion);
  };

  const handleFeedbackSubmitted = (feedback: Ticket) => {
    setPendingFeedback(feedback);
  };

  const selectedOrg =
    managerOrgs.find((org) => org.id === scope.orgId) ?? managerOrgs[0];
  const headerDescription = selectedOrg?.name
    ? `Manage your organization, ${selectedOrg.name}.`
    : managerOrgName
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
        return (
          <OrganizationsPanel
            mode='manager'
            onOrganizationRemoved={() => {
              void loadManagerStatus();
            }}
          />
        );
    }
  }, [activeSection, loadManagerStatus, pendingFeedback, pendingSuggestion]);

  // Loading state
  if (view === 'loading' || isLoading) {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <StatusBanner variant='info' kind='info'>
          Loading your account information...
        </StatusBanner>
      </main>
    );
  }

  if (view === 'error') {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <div className='w-full space-y-4'>
          <StatusBanner variant='error' kind='error'>
            {error || 'Failed to load your organization.'}
          </StatusBanner>
          <Button
            type='button'
            variant='secondary'
            onClick={() => {
              void loadManagerStatus();
            }}
          >
            Retry
          </Button>
        </div>
      </main>
    );
  }

  if (view !== 'dashboard') {
    return <AccountHome />;
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
        <StatusBanner variant='error' kind='error'>
          {authError}
        </StatusBanner>
      )}
      {error ? (
        <StatusBanner variant='error' kind='error'>
          {error}
        </StatusBanner>
      ) : null}
      {managerOrgs.length > 1 ? (
        <div className='mb-4 max-w-sm space-y-1'>
          <Label htmlFor='manager-org-switcher'>Organization</Label>
          <Select
            id='manager-org-switcher'
            aria-label='Organization'
            value={scope.orgId ?? ''}
            onChange={(event) => {
              scope.setOrg(event.target.value);
            }}
          >
            {managerOrgs.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </Select>
        </div>
      ) : null}
      <div>{activeContent}</div>
    </AppShell>
  );
}
