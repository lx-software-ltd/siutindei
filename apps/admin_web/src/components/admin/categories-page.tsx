'use client';

import { parseAsString, useQueryStates } from 'nuqs';

import { ActivityCategoriesPanel } from '../shared';
import { AdminTabStrip } from '../ui/admin-tab-strip';
import { CategoryChecksPanel } from './category-suggestions/category-checks-panel';
import { CategorySuggestionsPanel } from './category-suggestions/category-suggestions-panel';

type CategoryView = 'categories' | 'suggestions' | 'checks';

const CATEGORY_VIEWS = [
  { key: 'categories' as const, label: 'Categories' },
  { key: 'suggestions' as const, label: 'Category Suggestions' },
  { key: 'checks' as const, label: 'Category Checks' },
];

export function CategoriesPage() {
  const [query, setQuery] = useQueryStates({
    section: parseAsString,
    categoryView: parseAsString,
  });
  const activeView: CategoryView =
    query.categoryView === 'suggestions' ||
    query.categoryView === 'categories' ||
    query.categoryView === 'checks'
      ? query.categoryView
      : query.section === 'category-suggestions'
        ? 'suggestions'
        : 'categories';

  return (
    <div className='space-y-4'>
      <AdminTabStrip
        aria-label='Categories'
        items={CATEGORY_VIEWS}
        activeKey={activeView}
        onChange={(key) => {
          void setQuery({
            section: 'activity-categories',
            categoryView: key === 'categories' ? null : key,
          });
        }}
      />
      {activeView === 'suggestions' ? (
        <CategorySuggestionsPanel />
      ) : activeView === 'checks' ? (
        <CategoryChecksPanel />
      ) : (
        <ActivityCategoriesPanel />
      )}
    </div>
  );
}
