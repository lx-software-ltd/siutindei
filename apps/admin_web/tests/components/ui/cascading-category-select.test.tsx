import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CascadingCategorySelect } from '@/components/ui/cascading-category-select';
import { useActivityCategories } from '@/hooks/use-activity-categories';
import type { ActivityCategoryNode } from '@/lib/api-client';
import {
  insertActivityCategory,
  resetPublishedActivityCategories,
} from '@/lib/activity-category-tree';

const fetchActivityCategories = vi.fn();
const createResource = vi.fn();

vi.mock('@/lib/api-client', () => ({
  fetchActivityCategories: (...args: unknown[]) => fetchActivityCategories(...args),
  createResource: (...args: unknown[]) => createResource(...args),
}));

const ADD_LABEL = '— Add a new subcategory —';

function sportTree(): ActivityCategoryNode[] {
  return [
    {
      id: 'cat-sport',
      parent_id: null,
      name: 'Sport',
      name_translations: { en: 'Sport' },
      display_order: 1,
      children: [
        {
          id: 'cat-water',
          parent_id: 'cat-sport',
          name: 'Water Sports',
          name_translations: { en: 'Water Sports' },
          display_order: 1,
          children: [],
        },
      ],
    },
    {
      id: 'cat-arts',
      parent_id: null,
      name: 'Arts',
      name_translations: { en: 'Arts' },
      display_order: 2,
      children: [],
    },
    {
      id: 'cat-pending',
      parent_id: null,
      name: 'Pending categorisation',
      name_translations: { en: 'Pending categorisation' },
      display_order: 3,
      is_system: true,
      children: [
        {
          id: 'cat-legacy',
          parent_id: 'cat-pending',
          name: 'Legacy',
          name_translations: { en: 'Legacy' },
          display_order: 1,
          children: [],
        },
      ],
    },
  ];
}

function ActivitySelect({
  label,
  value,
  onChange,
  allowNewSubcategory = true,
}: {
  label: string;
  value: string;
  onChange: (categoryId: string) => void;
  allowNewSubcategory?: boolean;
}) {
  const { tree } = useActivityCategories();
  return (
    <section aria-label={label}>
      <CascadingCategorySelect
        tree={tree}
        value={value}
        onChange={onChange}
        allowNewSubcategory={allowNewSubcategory}
      />
    </section>
  );
}

function TwoActivities() {
  const [left, setLeft] = useState('cat-sport');
  const [right, setRight] = useState('cat-sport');
  return (
    <>
      <ActivitySelect label='First activity' value={left} onChange={setLeft} />
      <ActivitySelect label='Second activity' value={right} onChange={setRight} />
    </>
  );
}

describe('insertActivityCategory', () => {
  it('appends a child under its parent', () => {
    const next = insertActivityCategory(sportTree(), {
      id: 'cat-kayak',
      parent_id: 'cat-sport',
      name: 'Kayaking',
      name_translations: { en: 'Kayaking' },
      display_order: 2,
      children: [],
    });
    const sport = next.find((node) => node.id === 'cat-sport');
    expect(sport?.children.map((child) => child.name)).toEqual([
      'Water Sports',
      'Kayaking',
    ]);
    expect(sportTree()[0].children).toHaveLength(1);
  });
});

describe('CascadingCategorySelect add subcategory', () => {
  beforeEach(() => {
    resetPublishedActivityCategories();
    fetchActivityCategories.mockImplementation(async () => ({
      items: structuredClone(sportTree()),
    }));
    createResource.mockImplementation(
      async (
        _resource: string,
        payload: { name: string; parent_id: string; display_order: number }
      ) => ({
        id: 'cat-kayak',
        parent_id: payload.parent_id,
        name: payload.name,
        name_translations: { en: payload.name },
        display_order: payload.display_order,
        is_system: false,
      })
    );
  });

  it('offers a new subcategory on the subcategory list only', async () => {
    render(<TwoActivities />);
    const first = () => within(screen.getByRole('region', { name: 'First activity' }));
    await waitFor(() => {
      expect(first().getByLabelText('Subcategory')).toBeVisible();
    });

    const categoryNames = [...first().getByLabelText('Category').querySelectorAll('option')].map(
      (option) => option.textContent
    );
    expect(categoryNames).not.toContain(ADD_LABEL);
    const subcategoryNames = [
      ...first().getByLabelText('Subcategory').querySelectorAll('option'),
    ].map((option) => option.textContent);
    expect(subcategoryNames).toContain('Water Sports');
    expect(subcategoryNames).toContain(ADD_LABEL);
  });

  it('creates the subcategory and lists it on the other dropdown', async () => {
    const user = userEvent.setup();
    render(<TwoActivities />);
    const first = () => within(screen.getByRole('region', { name: 'First activity' }));
    const second = () => within(screen.getByRole('region', { name: 'Second activity' }));
    await waitFor(() => {
      expect(first().getByLabelText('Subcategory')).toBeVisible();
    });

    await user.selectOptions(first().getByLabelText('Subcategory'), ADD_LABEL);
    expect(first().getByLabelText('Subcategory')).toHaveValue('__add_subcategory__');
    expect(second().getByLabelText('Subcategory')).toHaveValue('');

    await user.click(first().getByRole('button', { name: 'Add subcategory' }));
    expect(first().getByText('Enter a subcategory name.')).toBeVisible();
    expect(createResource).not.toHaveBeenCalled();

    await user.type(first().getByLabelText('New subcategory'), 'Kayaking');
    await user.click(first().getByRole('button', { name: 'Add subcategory' }));

    await waitFor(() => {
      expect(first().getByLabelText('Subcategory')).toHaveValue('cat-kayak');
    });
    expect(createResource).toHaveBeenCalledWith('activity-categories', {
      name: 'Kayaking',
      parent_id: 'cat-sport',
      display_order: 2,
    });
    expect(second().getByRole('option', { name: 'Kayaking' })).toBeInTheDocument();
    await user.selectOptions(second().getByLabelText('Subcategory'), 'Kayaking');
    expect(second().getByLabelText('Subcategory')).toHaveValue('cat-kayak');
  });

  it('shows the add field for a category that has no subcategories yet', async () => {
    const user = userEvent.setup();
    render(<TwoActivities />);
    const first = () => within(screen.getByRole('region', { name: 'First activity' }));
    await waitFor(() => {
      expect(first().getByLabelText('Category')).toBeVisible();
    });
    await user.selectOptions(first().getByLabelText('Category'), 'Arts');
    expect(first().getByLabelText('Subcategory')).toBeVisible();
    expect(first().getByRole('option', { name: ADD_LABEL })).toBeInTheDocument();
  });

  it('hides the add option for pending categorisation and for managers', async () => {
    const user = userEvent.setup();
    function Harness() {
      const [value, setValue] = useState('cat-pending');
      return (
        <ActivitySelect
          label='Manager activity'
          value={value}
          onChange={setValue}
          allowNewSubcategory={false}
        />
      );
    }
    const { rerender } = render(<Harness />);
    const manager = () => within(screen.getByRole('region', { name: 'Manager activity' }));
    await waitFor(() => {
      expect(manager().getByLabelText('Subcategory')).toBeVisible();
    });
    expect(manager().queryByRole('option', { name: ADD_LABEL })).not.toBeInTheDocument();

    function AdminPending() {
      const [value, setValue] = useState('cat-pending');
      return (
        <ActivitySelect label='Pending activity' value={value} onChange={setValue} />
      );
    }
    rerender(<AdminPending />);
    const pending = () => within(screen.getByRole('region', { name: 'Pending activity' }));
    await waitFor(() => {
      expect(pending().getByLabelText('Subcategory')).toBeVisible();
    });
    expect(pending().queryByRole('option', { name: ADD_LABEL })).not.toBeInTheDocument();
    await user.selectOptions(pending().getByLabelText('Category'), 'Arts');
    expect(pending().getByRole('option', { name: ADD_LABEL })).toBeInTheDocument();
  });
});
