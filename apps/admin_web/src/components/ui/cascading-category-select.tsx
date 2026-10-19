'use client';
import { formErrorClassName, RequiredMark } from './admin-field-grid';
import { AdminInlineError } from './admin-inline-error';

import { useId, useMemo, useState } from 'react';

import type { ActivityCategoryNode } from '../../lib/api-client';
import { createResource } from '../../lib/api-client';
import { publishActivityCategory } from '../../lib/activity-category-tree';
import { Button } from './button';
import { Input } from './input';
import { Label } from './label';
import { Select } from './select';

export const ADD_SUBCATEGORY_VALUE = '__add_subcategory__';
export const ADD_SUBCATEGORY_LABEL = '— Add a new subcategory —';

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
  /**
   * Admins can create a subcategory under the selected category.
   * Managers leave this off.
   */
  allowNewSubcategory?: boolean;
}

interface CreatedCategory {
  id: string;
  parent_id?: string | null;
  name: string;
  name_translations?: Record<string, string>;
  display_order?: number;
  is_system?: boolean;
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
  allowNewSubcategory = true,
}: CascadingCategorySelectProps) {
  const fieldId = useId();
  const [overrideState, setOverrideState] = useState<{
    forValue: string;
    selections: string[];
  } | null>(null);
  const [addingLevel, setAddingLevel] = useState<number | null>(null);
  const [draftName, setDraftName] = useState('');
  const [addError, setAddError] = useState('');
  const [saving, setSaving] = useState(false);

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
      if (!parent) {
        break;
      }
      const children = parent.children ?? [];
      const canStartHere =
        allowNewSubcategory && !parent.is_system && depth === 1;
      if (children.length === 0 && !canStartHere) {
        break;
      }
      const label = depth === 1 ? 'Subcategory' : `Subcategory ${depth}`;
      nextLevels.push({
        label,
        options: children,
        index: depth,
      });
      parentId = selections[depth];
      depth++;
    }
    return nextLevels;
  }, [allowNewSubcategory, nodesById, selections, tree]);

  const choose = (
    levelIndex: number,
    selectedId: string,
    created?: ActivityCategoryNode
  ) => {
    let updated = selections.slice(0, levelIndex);
    if (selectedId) {
      updated = [...updated, selectedId];
    }
    setOverrideState({ forValue: value, selections: updated });

    const finalId = updated[updated.length - 1];
    if (!finalId) return;
    const chain = updated
      .map((id) =>
        created && id === created.id ? created : nodesById.get(id)
      )
      .filter(Boolean) as ActivityCategoryNode[];
    onChange(finalId, chain);
  };

  const handleSelect = (levelIndex: number, selectedId: string) => {
    if (selectedId === ADD_SUBCATEGORY_VALUE) {
      setAddingLevel(levelIndex);
      setDraftName('');
      setAddError('');
      return;
    }
    setAddingLevel(null);
    setDraftName('');
    setAddError('');
    choose(levelIndex, selectedId);
  };

  const addSubcategory = async (levelIndex: number) => {
    const parentId = selections[levelIndex - 1];
    const parent = parentId ? nodesById.get(parentId) : undefined;
    const name = draftName.trim();
    if (!parent || !parentId) {
      setAddError('Select a category before adding a subcategory.');
      return;
    }
    if (!name) {
      setAddError('Enter a subcategory name.');
      return;
    }
    const siblings = parent.children ?? [];
    const folded = name.toLocaleLowerCase();
    if (siblings.some((child) => child.name.trim().toLocaleLowerCase() === folded)) {
      setAddError('A subcategory with this name already exists.');
      return;
    }
    const displayOrder =
      siblings.reduce((max, child) => Math.max(max, child.display_order ?? 0), 0) + 1;
    setSaving(true);
    setAddError('');
    try {
      const created = await createResource<
        { name: string; parent_id: string; display_order: number },
        CreatedCategory
      >('activity-categories', {
        name,
        parent_id: parentId,
        display_order: displayOrder,
      });
      const node: ActivityCategoryNode = {
        id: created.id,
        parent_id: created.parent_id ?? parentId,
        name: created.name,
        name_translations: created.name_translations ?? { en: created.name },
        display_order: created.display_order ?? displayOrder,
        is_system: Boolean(created.is_system),
        children: [],
      };
      publishActivityCategory(node);
      setAddingLevel(null);
      setDraftName('');
      choose(levelIndex, node.id, node);
    } catch (err) {
      setAddError(
        err instanceof Error && err.message
          ? err.message
          : 'Could not add the subcategory.'
      );
    } finally {
      setSaving(false);
    }
  };

  const errorId = errorMessage
    ? `category-select-error-${value || 'new'}`
    : undefined;
  const errorClassName = hasError
    ? formErrorClassName
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
          const parent =
            level.index > 0
              ? nodesById.get(selections[level.index - 1] ?? '')
              : undefined;
          const showAdd = Boolean(
            allowNewSubcategory && parent && !parent.is_system
          );
          const selectId = `${fieldId}-level-${level.index}`;
          const addingHere = addingLevel === level.index;
          return (
            <div key={`${level.label}-${level.index}`}>
              <Label htmlFor={selectId}>
                {level.label}
                {required ? <RequiredMark /> : null}
              </Label>
              <Select
                id={selectId}
                value={
                  addingHere
                    ? ADD_SUBCATEGORY_VALUE
                    : selections[level.index] || ''
                }
                onChange={(e) => handleSelect(level.index, e.target.value)}
                disabled={isLevelDisabled || saving}
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
                {showAdd ? (
                  <option value={ADD_SUBCATEGORY_VALUE}>
                    {ADD_SUBCATEGORY_LABEL}
                  </option>
                ) : null}
              </Select>
              {showAdd && addingHere ? (
                <div className='mt-2 space-y-2'>
                  <Label htmlFor={`${selectId}-new`}>New subcategory</Label>
                  <Input
                    id={`${selectId}-new`}
                    value={draftName}
                    disabled={disabled || saving}
                    onChange={(event) => {
                      setDraftName(event.target.value);
                      if (addError) setAddError('');
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        void addSubcategory(level.index);
                      }
                    }}
                  />
                  <Button
                    type='button'
                    size='sm'
                    loading={saving}
                    disabled={disabled}
                    onClick={() => void addSubcategory(level.index)}
                  >
                    Add subcategory
                  </Button>
                  {addError ? (
                    <AdminInlineError size='xs'>{addError}</AdminInlineError>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      {errorMessage ? (
        <AdminInlineError id={errorId} size='xs'>
          {errorMessage}
        </AdminInlineError>
      ) : null}
    </div>
  );
}
