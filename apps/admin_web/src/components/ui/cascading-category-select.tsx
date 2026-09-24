'use client';

import { useMemo, useState } from 'react';

import type { ActivityCategoryNode } from '../../lib/api-client';
import { Label } from './label';
import { Select } from './select';

interface CascadingCategorySelectProps {
  /** The full category tree from useActivityCategories(). */
  tree: ActivityCategoryNode[];
  /** Currently selected category_id (if editing). */
  value: string;
  /** Called when the user picks any category. */
  onChange: (categoryId: string, chain: ActivityCategoryNode[]) => void;
  /** Whether the controls are disabled. */
  disabled?: boolean;
  /** Whether selection is required. */
  required?: boolean;
  /** Whether to show an error state. */
  hasError?: boolean;
  /** Error message to display under the selects. */
  errorMessage?: string;
  /** Extra classes applied to each select. */
  selectClassName?: string;
}

/**
 * Renders a dynamic set of cascading <select> dropdowns
 * for arbitrary category depths.
 */
export function CascadingCategorySelect({
  tree,
  value,
  onChange,
  disabled,
  required = false,
  hasError = false,
  errorMessage,
  selectClassName = '',
}: CascadingCategorySelectProps) {
  const [overrideState, setOverrideState] = useState<{
    forValue: string;
    selections: string[];
  } | null>(null);

  const nodesById = useMemo(() => {
    const map = new Map<string, ActivityCategoryNode>();
    function walk(nodes: ActivityCategoryNode[]) {
      for (const node of nodes) {
        map.set(node.id, node);
        if (node.children) walk(node.children);
      }
    }
    walk(tree);
    return map;
  }, [tree]);

  const derivedSelections = useMemo(() => {
    if (!value || nodesById.size === 0) {
      return [];
    }
    const chain: string[] = [];
    let current = nodesById.get(value);
    while (current) {
      chain.unshift(current.id);
      current = current.parent_id
        ? nodesById.get(current.parent_id)
        : undefined;
    }
    return chain;
  }, [value, nodesById]);

  const selections =
    overrideState && overrideState.forValue === value
      ? overrideState.selections
      : derivedSelections;

  const levels = useMemo(() => {
    const nextLevels: {
      label: string;
      options: ActivityCategoryNode[];
      index: number;
    }[] = [];

    nextLevels.push({
      label: 'Category',
      options: tree,
      index: 0,
    });

    let parentId = selections[0];
    let depth = 1;
    while (parentId) {
      const parent = nodesById.get(parentId);
      if (!parent || !parent.children || parent.children.length === 0) {
        break;
      }
      const label = depth === 1 ? 'Subcategory' : `Subcategory ${depth}`;
      nextLevels.push({
        label,
        options: parent.children,
        index: depth,
      });
      parentId = selections[depth];
      depth++;
    }
    return nextLevels;
  }, [nodesById, selections, tree]);

  const handleSelect = (levelIndex: number, selectedId: string) => {
    let updated = selections.slice(0, levelIndex);
    if (selectedId) {
      updated = [...updated, selectedId];
    }
    setOverrideState({ forValue: value, selections: updated });

    const finalId = updated[updated.length - 1];
    if (!finalId) return;
    const chain = updated
      .map((id) => nodesById.get(id))
      .filter(Boolean) as ActivityCategoryNode[];
    onChange(finalId, chain);
  };

  const errorId = errorMessage
    ? `category-select-error-${value || 'new'}`
    : undefined;
  const errorClassName = hasError
    ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
    : '';
  const selectClasses = [selectClassName, errorClassName]
    .filter(Boolean)
    .join(' ');

  return (
    <div className='space-y-1'>
      <div className='grid gap-4 md:grid-cols-2'>
        {levels.map((level) => {
          const isLevelDisabled =
            disabled || (level.index > 0 && !selections[level.index - 1]);
          return (
            <div key={`${level.label}-${level.index}`}>
              <Label htmlFor={`category-level-${level.index}`}>
                {level.label}
                {required ? (
                  <span className='ml-1 text-red-500' aria-hidden='true'>
                    *
                  </span>
                ) : null}
              </Label>
              <Select
                id={`category-level-${level.index}`}
                value={selections[level.index] || ''}
                onChange={(e) => handleSelect(level.index, e.target.value)}
                disabled={isLevelDisabled}
                className={selectClasses}
                aria-invalid={hasError || undefined}
                aria-describedby={errorId}
              >
                <option value=''>
                  Select {level.label.toLowerCase()}
                </option>
                {level.options.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.is_system ? `${opt.name} (pending)` : opt.name}
                  </option>
                ))}
              </Select>
            </div>
          );
        })}
      </div>
      {errorMessage ? (
        <p id={errorId} className='text-xs text-red-600'>
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
