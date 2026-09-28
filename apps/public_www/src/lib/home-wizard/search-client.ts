import { HOME_WIZARD_SEARCH_LIMIT } from '@/lib/activities/search-limits';
import { fetchActivitySearch } from '@/lib/activities/search-client';
import type { ActivityListing } from '@/lib/activities/types';

export type ActivitySearchResult = ActivityListing;

export interface SearchActivity {
  readonly id: string;
  readonly name: string;
  readonly description: string | null;
  readonly categoryId: string | null;
}

export interface SearchLocation {
  readonly areaId: string;
  readonly regionAreaId: string | null;
}

export interface SearchOrganization {
  readonly name: string;
}

export interface ActivitySearchResponse {
  readonly items: readonly ActivitySearchResult[];
}

export async function fetchActivitiesForWizard(params: {
  readonly age: number;
  readonly categoryIds: readonly string[];
}): Promise<ActivitySearchResponse> {
  const response = await fetchActivitySearch({
    age: params.age,
    categoryIds: params.categoryIds,
    limit: HOME_WIZARD_SEARCH_LIMIT,
  });
  return { items: response.items };
}
