'use client';

import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../../lib/api-client';
import {
  getUserAccessStatus,
  getUserFeedback,
  getUserSuggestions,
  type Ticket,
} from '../../lib/api-client-user';
import { useAuth } from '../auth-provider';
import { AppShell } from '../app-shell';
import { StatusBanner } from '../status-banner';
import { AccessRequestForm } from './access-request-form';
import { PendingRequestNotice } from './pending-request-notice';
import { FeedbackForm } from './feedback-form';
import { PendingFeedbackNotice } from './pending-feedback-notice';
import { SuggestionForm } from './suggestion-form';
import { PendingSuggestionNotice } from './pending-suggestion-notice';

const sectionLabels = [
  { key: 'become-manager', label: 'Become a Manager' },
  { key: 'suggest-place', label: 'Suggest a Place' },
  { key: 'feedback', label: 'Feedback' },
];

/**
 * Account home for people who do not manage an organization yet.
 * Managers with no organization and plain users share this screen.
 */
export function AccountHome() {
  const { user, logout, error: authError } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeSection, setActiveSection] = useState('suggest-place');

  // Access request state
  const [pendingRequest, setPendingRequest] = useState<Ticket | null>(null);

  // Suggestion state
  const [pendingSuggestion, setPendingSuggestion] =
    useState<Ticket | null>(null);
  const [pendingFeedback, setPendingFeedback] = useState<Ticket | null>(null);

  const loadUserStatus = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      // Load both access request status and suggestions in parallel
      const [accessStatus, suggestionsStatus, feedbackStatus] =
        await Promise.all([
          getUserAccessStatus(),
          getUserSuggestions(),
          getUserFeedback(),
        ]);

      // Check for pending access request
      if (accessStatus.has_pending_request && accessStatus.pending_request) {
        setPendingRequest(accessStatus.pending_request);
      }

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
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to load your account status.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUserStatus();
  }, [loadUserStatus]);

  const handleRequestSubmitted = (request: Ticket) => {
    setPendingRequest(request);
  };

  const handleSuggestionSubmitted = (suggestion: Ticket) => {
    setPendingSuggestion(suggestion);
  };

  const handleFeedbackSubmitted = (feedback: Ticket) => {
    setPendingFeedback(feedback);
  };

  // Loading state
  if (isLoading) {
    return (
      <main className='mx-auto flex min-h-screen max-w-lg items-center px-6'>
        <StatusBanner kind='info'>
          Loading your account information...
        </StatusBanner>
      </main>
    );
  }

  // Render the active section content
  const renderContent = () => {
    if (activeSection === 'become-manager') {
      if (pendingRequest) {
        return <PendingRequestNotice request={pendingRequest} />;
      }
      return <AccessRequestForm onRequestSubmitted={handleRequestSubmitted} />;
    }

    if (activeSection === 'suggest-place') {
      if (pendingSuggestion) {
        return <PendingSuggestionNotice suggestion={pendingSuggestion} />;
      }
      return <SuggestionForm onSuggestionSubmitted={handleSuggestionSubmitted} />;
    }

    if (activeSection === 'feedback') {
      if (pendingFeedback) {
        return <PendingFeedbackNotice feedback={pendingFeedback} />;
      }
      return <FeedbackForm onFeedbackSubmitted={handleFeedbackSubmitted} />;
    }

    return null;
  };

  return (
    <AppShell
      sections={sectionLabels}
      activeKey={activeSection}
      onSelect={setActiveSection}
      onLogout={logout}
      userEmail={user?.email}
      lastAuthTime={user?.lastAuthTime}
    >
      {authError && (
        <StatusBanner kind='error'>
          {authError}
        </StatusBanner>
      )}
      {error && (
        <StatusBanner kind='error'>
          {error}
        </StatusBanner>
      )}
      {renderContent()}
    </AppShell>
  );
}
