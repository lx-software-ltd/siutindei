import type { FeedbackLabel } from '../types/admin';
import type { Ticket } from './api-client-tickets';
import { buildApiUrl, request } from './api-client-core';
export type { Ticket } from './api-client-tickets';

export interface NominatimAddress {
  road?: string;
  house_number?: string;
  suburb?: string;
  quarter?: string;
  neighbourhood?: string;
  city_district?: string;
  city?: string;
  town?: string;
  village?: string;
  state?: string;
  county?: string;
  country?: string;
  country_code?: string;
  postcode?: string;
  [key: string]: string | undefined;
}

export interface NominatimResult {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
  address: NominatimAddress;
  type: string;
}

export interface AddressSearchResponse {
  items: NominatimResult[];
}

export interface ManagerStatusResponse {
  organizations_count: number;
  has_pending_request: boolean;
  pending_request?: Ticket | null;
}

export interface SubmitAccessRequestPayload {
  organization_name: string;
  request_message?: string;
}

export interface SubmitAccessRequestResponse {
  message: string;
  ticket_id: string;
}

export interface UserSuggestionsResponse {
  has_pending_suggestion: boolean;
  suggestions: Ticket[];
}

export interface SubmitSuggestionPayload {
  organization_name: string;
  description?: string;
  suggested_district?: string;
  suggested_address?: string;
  suggested_lat?: number;
  suggested_lng?: number;
  media_urls?: string[];
  additional_notes?: string;
}

export interface SubmitSuggestionResponse {
  message: string;
  ticket_id: string;
}

export interface OrganizationLookup {
  id: string;
  name: string;
}

export interface OrganizationLookupListResponse {
  items: OrganizationLookup[];
}

export interface UserFeedbackResponse {
  has_pending_feedback: boolean;
  feedbacks: Ticket[];
}

export interface UserFeedbackCreatePayload {
  organization_id: string;
  stars: number;
  label_ids?: string[];
  description?: string;
}

export interface UserFeedbackSubmitResponse {
  message: string;
  ticket_id: string;
}

export interface GeographicAreaNode {
  id: string;
  parent_id: string | null;
  name: string;
  name_translations: Record<string, string>;
  level: 'country' | 'region' | 'city' | 'district';
  code: string | null;
  active: boolean;
  display_order: number;
  children: GeographicAreaNode[];
}

export interface ActivityCategoryNode {
  id: string;
  parent_id: string | null;
  name: string;
  name_translations: Record<string, string>;
  display_order: number;
  is_system?: boolean;
  children: ActivityCategoryNode[];
}

function buildUserUrl(resource: string, id?: string) {
  return id
    ? buildApiUrl(`v1/user/${resource}/${id}`)
    : buildApiUrl(`v1/user/${resource}`);
}

export async function searchAddress(
  query: string,
  options: { countryCodes?: string; limit?: number } = {}
): Promise<NominatimResult[]> {
  const url = new URL(buildUserUrl('address-search'));
  url.searchParams.set('q', query);
  if (options.countryCodes) {
    url.searchParams.set('countrycodes', options.countryCodes);
  }
  if (options.limit) {
    url.searchParams.set('limit', `${options.limit}`);
  }
  const response = await request<AddressSearchResponse>(url.toString());
  return response.items;
}

export async function getUserAccessStatus(): Promise<ManagerStatusResponse> {
  return request<ManagerStatusResponse>(
    buildUserUrl('access-request')
  );
}

export async function submitAccessRequest(
  payload: SubmitAccessRequestPayload
): Promise<SubmitAccessRequestResponse> {
  return request<SubmitAccessRequestResponse>(buildUserUrl('access-request'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function getUserSuggestions(): Promise<UserSuggestionsResponse> {
  return request<UserSuggestionsResponse>(
    buildUserUrl('organization-suggestion')
  );
}

export async function submitOrganizationSuggestion(
  payload: SubmitSuggestionPayload
): Promise<SubmitSuggestionResponse> {
  return request<SubmitSuggestionResponse>(
    buildUserUrl('organization-suggestion'),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  );
}

export async function listFeedbackLabels(): Promise<{
  items: FeedbackLabel[];
}> {
  return request<{ items: FeedbackLabel[] }>(
    buildUserUrl('feedback-labels')
  );
}

export async function searchUserOrganizations(
  query: string,
  limit = 10
): Promise<OrganizationLookupListResponse> {
  const url = new URL(buildUserUrl('organizations'));
  url.searchParams.set('q', query);
  url.searchParams.set('limit', `${limit}`);
  return request<OrganizationLookupListResponse>(url.toString());
}

export async function getUserFeedback(): Promise<UserFeedbackResponse> {
  return request<UserFeedbackResponse>(buildUserUrl('organization-feedback'));
}

export async function submitUserFeedback(
  payload: UserFeedbackCreatePayload
): Promise<UserFeedbackSubmitResponse> {
  return request<UserFeedbackSubmitResponse>(buildUserUrl('organization-feedback'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
}

export async function fetchActiveAreas(): Promise<{ items: GeographicAreaNode[] }> {
  return request<{ items: GeographicAreaNode[] }>(
    buildUserUrl('areas')
  );
}

export async function fetchActivityCategories(): Promise<{
  items: ActivityCategoryNode[];
}> {
  return request<{ items: ActivityCategoryNode[] }>(
    buildUserUrl('activity-categories')
  );
}
