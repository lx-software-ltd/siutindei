'use client';

import { parseAsString, useQueryStates } from 'nuqs';

import { ActivityCategoriesPanel } from '../shared';
import { AdminTabStrip } from '../ui/admin-tab-strip';
import { CategorySuggestionsPanel } from './category-suggestions/category-suggestions-panel';

type CategoryView = 'categories' | 'suggestions';

const CATEGORY_VIEWS = [
  { key: 'categories' as const, label: 'Categories' },
  { key: 'suggestions' as const, label: 'Category Suggestions' },
];

export function CategoriesPage() {
  const [query, setQuery] = useQueryStates({
    section: parseAsString,
    categoryView: parseAsString,
  });
  const activeView: CategoryView =
    query.categoryView === 'suggestions' || query.categoryView === 'categories'
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
            categoryView: key === 'categories' ? null : 'suggestions',
          });
        }}
      />
      {activeView === 'suggestions' ? (
        <CategorySuggestionsPanel />
      ) : (
        <ActivityCategoriesPanel />
      )}
    </div>
  );
}
