'use client';
import { AdminInlineError } from '../ui/admin-inline-error';

import { useState } from 'react';

import {
  ApiError,
} from '../../lib/api-client';
import { useFormValidation } from '../../hooks/use-form-validation';
import { submitAccessRequest, type Ticket } from '../../lib/api-client-user';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { StatusBanner } from '../status-banner';

interface AccessRequestFormProps {
  onRequestSubmitted: (request: Ticket) => void;
}

export function AccessRequestForm({ onRequestSubmitted }: AccessRequestFormProps) {
  const [organizationName, setOrganizationName] = useState('');
  const [requestMessage, setRequestMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const validation = useFormValidation(
    ['organizationName'],
    null
  );

  const orgNameError = organizationName.trim()
    ? ''
    : 'Enter an organization name.';
  const showOrgNameError = validation.shouldShowError(
    'organizationName',
    Boolean(orgNameError)
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    validation.setHasSubmitted(true);
    validation.markAllTouched();

    if (!organizationName.trim()) {
      setError('Organization name is required.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const response = await submitAccessRequest({
        organization_name: organizationName.trim(),
        request_message: requestMessage.trim() || undefined,
      });
      // Backend returns { message, ticket_id } for async processing.
      // Construct a partial Ticket from known data for the pending notice.
      onRequestSubmitted({
        id: '',
        ticket_id: response.ticket_id,
        ticket_type: 'access_request',
        organization_name: organizationName.trim(),
        message: requestMessage.trim() || null,
        status: 'pending',
        submitter_email: '',
        submitter_id: '',
        created_at: new Date().toISOString(),
        reviewed_at: null,
        reviewed_by: null,
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to submit request. Please try again.';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className='space-y-4'>
      <Card
        title='Request Organization Access'
        description='You are not currently associated with any organization. Please submit a request to be added to an existing organization or to create a new one.'
      >
        {error && (
          <div className='mb-4'>
            <StatusBanner variant='error' kind='error'>
              {error}
            </StatusBanner>
          </div>
        )}

        <form onSubmit={handleSubmit} className='space-y-4'>
          <div className='space-y-1'>
            <Label htmlFor='organization-name'>
              Organization Name{' '}
              {validation.requiredIndicator}
            </Label>
            <Input
              id='organization-name'
              type='text'
              value={organizationName}
              onChange={(e) => {
                validation.markTouched('organizationName');
                setOrganizationName(e.target.value);
              }}
              placeholder={
                'Enter the name of the organization you want to join or ' +
                'create'
              }
              disabled={isSubmitting}
              className={validation.errorClassName(
                'organizationName',
                Boolean(orgNameError)
              )}
              aria-invalid={showOrgNameError || undefined}
              onBlur={() => validation.markTouched('organizationName')}
            />
            {showOrgNameError ? (
              <AdminInlineError size='xs'>{orgNameError}</AdminInlineError>
            ) : null}
            <p className='text-sm text-slate-500'>
              Enter the exact name of an existing organization, or the name for a
              new organization you would like to create.
            </p>
          </div>

          <div>
            <Label htmlFor='request-message'>Request Message (Optional)</Label>
            <Textarea
              id='request-message'
              rows={4}
              value={requestMessage}
              onChange={(e) => setRequestMessage(e.target.value)}
              placeholder='Provide any additional information about your request...'
              disabled={isSubmitting}
            />
            <p className='mt-1 text-sm text-slate-500'>
              Explain why you need access to this organization or provide
              additional context for your request.
            </p>
          </div>

          <div className='pt-2'>
            <Button
              type='submit'
              loading={isSubmitting}
              loadingLabel='Submitting…'
              className='w-full sm:w-auto'
            >
              Submit Request
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
