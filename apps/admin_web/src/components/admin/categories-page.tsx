'use client';

import { useEffect } from 'react';
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
    tab: parseAsString,
  });

  useEffect(() => {
    if (query.categoryView !== 'checks') {
      return;
    }
    void setQuery({
      section: 'data-quality',
      categoryView: null,
      tab: 'checks',
    });
  }, [query.categoryView, setQuery]);

  const activeView: CategoryView =
    query.categoryView === 'suggestions'
      ? 'suggestions'
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
      ) : (
        <ActivityCategoriesPanel />
      )}
    </div>
  );
}
