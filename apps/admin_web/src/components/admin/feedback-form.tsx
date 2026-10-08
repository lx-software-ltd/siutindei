'use client';

import { useEffect, useMemo, useState, type FormEvent } from 'react';

import { ApiError } from '../../lib/api-client';
import {
  listFeedbackLabels,
  searchUserOrganizations,
  submitUserFeedback,
  type Ticket,
  type UserFeedbackCreatePayload,
} from '../../lib/api-client-user';
import type { FeedbackLabel } from '../../types/admin';
import { useFormValidation } from '../../hooks/use-form-validation';
import { AdminField } from '../ui/admin-field-grid';
import { AdminToggleChip } from '../ui/admin-tab-strip';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import { StarRating } from '../ui/star-rating';
import { Textarea } from '../ui/textarea';
import { StatusBanner } from '../status-banner';

interface FeedbackFormProps {
  onFeedbackSubmitted: (feedback: Ticket) => void;
}

interface OrganizationOption {
  id: string;
  name: string;
}

export function FeedbackForm({ onFeedbackSubmitted }: FeedbackFormProps) {
  const [organizationQuery, setOrganizationQuery] = useState('');
  const [organizationMatches, setOrganizationMatches] = useState<
    OrganizationOption[]
  >([]);
  const [selectedOrganization, setSelectedOrganization] =
    useState<OrganizationOption | null>(null);
  const [labels, setLabels] = useState<FeedbackLabel[]>([]);
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [stars, setStars] = useState(1);
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState('');
  const validation = useFormValidation(
    ['organization', 'stars'] as const,
    selectedOrganization?.id ?? ''
  );

  useEffect(() => {
    const loadLabels = async () => {
      try {
        const response = await listFeedbackLabels();
        setLabels(response.items);
      } catch {
        setLabels([]);
      }
    };
    loadLabels();
  }, []);

  useEffect(() => {
    const trimmed = organizationQuery.trim();
    if (trimmed.length < 2) {
      setOrganizationMatches([]);
      return;
    }
    setIsSearching(true);
    const timer = window.setTimeout(async () => {
      try {
        const response = await searchUserOrganizations(trimmed, 10);
        setOrganizationMatches(response.items);
      } catch {
        setOrganizationMatches([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [organizationQuery]);

  const toggleLabel = (labelId: string) => {
    setSelectedLabels((prev) =>
      prev.includes(labelId)
        ? prev.filter((id) => id !== labelId)
        : [...prev, labelId]
    );
  };

  const selectedLabelNames = useMemo(() => {
    const map = new Map(labels.map((label) => [label.id, label.name]));
    return selectedLabels
      .map((id) => map.get(id))
      .filter((name): name is string => Boolean(name));
  }, [labels, selectedLabels]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    validation.setHasSubmitted(true);
    validation.markAllTouched();

    if (!selectedOrganization) {
      setError('Please select an organization.');
      return;
    }
    if (!Number.isInteger(stars) || stars < 1 || stars > 5) {
      setError('Stars must be a whole number between 1 and 5.');
      return;
    }

    const payload: UserFeedbackCreatePayload = {
      organization_id: selectedOrganization.id,
      stars,
      label_ids: selectedLabels,
      description: description.trim() || undefined,
    };

    setIsSubmitting(true);
    try {
      const response = await submitUserFeedback(payload);
      onFeedbackSubmitted({
        id: '',
        ticket_id: response.ticket_id,
        ticket_type: 'organization_feedback',
        organization_name: selectedOrganization.name,
        message: null,
        status: 'pending',
        submitter_id: '',
        submitter_email: '',
        created_at: new Date().toISOString(),
        reviewed_at: null,
        reviewed_by: null,
        admin_notes: null,
        media_urls: [],
        organization_id: selectedOrganization.id,
        feedback_stars: stars,
        feedback_label_ids: selectedLabels,
        feedback_text: description.trim() || null,
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to submit feedback. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const hasOrganizationError = validation.shouldShowError(
    'organization',
    !selectedOrganization
  );
  const hasStarsError = validation.shouldShowError(
    'stars',
    !Number.isInteger(stars) || stars < 1 || stars > 5
  );

  return (
    <Card
      title='Leave Feedback'
      description='Share your experience with an organization.'
    >
      {error && (
        <div className='mb-4'>
          <StatusBanner kind='error'>
            {error}
          </StatusBanner>
        </div>
      )}

      <form onSubmit={handleSubmit} className='space-y-4'>
        <AdminField
          label='Organization'
          htmlFor='feedback-org'
          required
          error={hasOrganizationError ? 'Please select an organization.' : undefined}
        >
          <Input
            id='feedback-org'
            className={validation.errorClassName('organization', !selectedOrganization)}
            value={organizationQuery}
            onChange={(e) => {
              setOrganizationQuery(e.target.value);
              setSelectedOrganization(null);
            }}
            onBlur={() => validation.markTouched('organization')}
            placeholder='Search organizations...'
          />
          {isSearching && (
            <p className='mt-1 text-xs text-slate-500'>Searching...</p>
          )}
          {organizationMatches.length > 0 && !selectedOrganization && (
            <div className='mt-2 rounded border border-slate-200 bg-white'>
              {organizationMatches.map((org) => (
                <button
                  key={org.id}
                  type='button'
                  onClick={() => {
                    setSelectedOrganization(org);
                    setOrganizationQuery(org.name);
                    setOrganizationMatches([]);
                  }}
                  className='flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50'
                >
                  <span>{org.name}</span>
                </button>
              ))}
            </div>
          )}
          {selectedOrganization && (
            <p className='mt-2 text-xs text-slate-500'>
              Selected: {selectedOrganization.name}
            </p>
          )}
        </AdminField>

        <AdminField
          label='Stars'
          required
          error={
            hasStarsError
              ? 'Stars must be a whole number between 1 and 5.'
              : undefined
          }
        >
          <div className='mt-2 flex items-center gap-2'>
            <StarRating
              value={stars}
              onChange={(value) => {
                setStars(value);
                validation.markTouched('stars');
              }}
            />
            <span className='text-sm text-slate-500'>{stars}/5</span>
          </div>
        </AdminField>

        <AdminField label='Labels'>
          {labels.length === 0 ? (
            <p className='text-sm text-slate-500'>
              No labels available.
            </p>
          ) : (
            <div className='mt-2 flex flex-wrap gap-2'>
              {labels.map((label) => {
                const isSelected = selectedLabels.includes(label.id);
                return (
                  <AdminToggleChip
                    key={label.id}
                    pressed={isSelected}
                    onClick={() => toggleLabel(label.id)}
                  >
                    {label.name}
                  </AdminToggleChip>
                );
              })}
            </div>
          )}
          {selectedLabelNames.length > 0 && (
            <p className='mt-2 text-xs text-slate-500'>
              Selected: {selectedLabelNames.join(', ')}
            </p>
          )}
        </AdminField>

        <AdminField label='Description' htmlFor='feedback-description'>
          <Textarea
            id='feedback-description'
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder='Share details about your experience...'
            maxLength={5000}
          />
        </AdminField>

        <div className='pt-2'>
          <Button
            type='submit'
            variant='primary'
            loading={isSubmitting}
            loadingLabel='Submitting…'
            className='w-full sm:w-auto'
          >
            Submit Feedback
          </Button>
        </div>
      </form>
    </Card>
  );
}
