'use client';
import { formErrorClassName, RequiredMark } from './admin-field-grid';
import { AdminInlineError } from './admin-inline-error';

import { useMemo, useState } from 'react';

import type { GeographicAreaNode } from '../../lib/api-client';
import { Label } from './label';
import { Select } from './select';

interface CascadingAreaSelectProps {
  /** The full area tree from useGeographicAreas(). */
  tree: GeographicAreaNode[];
  /** Currently selected leaf area_id (if editing an existing location). */
  value: string;
  /** Called when the user completes a selection (picks a leaf). */
  onChange: (areaId: string, chain: GeographicAreaNode[]) => void;
  /** Whether the controls are disabled. */
  disabled?: boolean;
  /** Whether to disable the country dropdown. */
  disableCountry?: boolean;
  /** Whether to render the country dropdown last. */
  showCountryLast?: boolean;
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
 * Renders a dynamic set of cascading <select> dropdowns that adapt
 * to the depth of the selected country in the geographic area tree.
 *
 * - Hong Kong: Country > Region > District > Neighbourhood
 * - Singapore: Country > District
 * - UAE: Country > Region > District
 */
export function CascadingAreaSelect({
  tree,
  value,
  onChange,
  disabled,
  disableCountry,
  showCountryLast,
  required = false,
  hasError = false,
  errorMessage,
  selectClassName = '',
}: CascadingAreaSelectProps) {
  // Track user-driven overrides and the last external value they were
  // computed from, so we can reset when the parent changes `value`.
  const [overrideState, setOverrideState] = useState<{
    forValue: string;
    selections: string[];
  } | null>(null);

  // Build a lookup map from the full tree
  const nodesById = useMemo(() => {
    const map = new Map<string, GeographicAreaNode>();
    function walk(nodes: GeographicAreaNode[]) {
      for (const node of nodes) {
        map.set(node.id, node);
        if (node.children) walk(node.children);
      }
    }
    walk(tree);
    return map;
  }, [tree]);

  // Derive the selections chain from the current `value` prop
  const derivedSelections = useMemo(() => {
    if (!value || nodesById.size === 0) {
      // Default to the single active country if there's only one
      return tree.length === 1 ? [tree[0].id] : [];
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
  }, [value, nodesById, tree]);

  // Use overrides only if they were computed for the current `value`
  const selections =
    overrideState && overrideState.forValue === value
      ? overrideState.selections
      : derivedSelections;

  // Get the options at each level.
  const levels = useMemo(() => {
    const nextLevels: {
      label: string;
      options: GeographicAreaNode[];
      index: number;
      isCountry?: boolean;
    }[] = [];

    // Level 0: countries (root nodes)
    nextLevels.push({
      label: 'Country',
      options: tree,
      index: 0,
      isCountry: true,
    });

    // Subsequent levels: children of the selected node at each depth
    let parentId = selections[0];
    let depth = 1;
    while (parentId) {
      const parent = nodesById.get(parentId);
      if (!parent || !parent.children || parent.children.length === 0) {
        break;
      }

      const childLevel = parent.children[0]?.level;
      const levelLabel =
        childLevel === 'region'
          ? 'Region'
          : childLevel === 'city'
            ? 'City'
            : childLevel === 'neighbourhood'
              ? 'Neighbourhood'
              : 'District';

      nextLevels.push({
        label: levelLabel,
        options: parent.children,
        index: depth,
      });

      parentId = selections[depth];
      depth++;
    }

    return nextLevels;
  }, [nodesById, selections, tree]);

  const handleSelect = (levelIndex: number, selectedId: string) => {
    let updated = [...selections.slice(0, levelIndex), selectedId];

    // Auto-drill if a node has only one child
    let node = nodesById.get(selectedId);
    while (node && node.children && node.children.length === 1) {
      const child = node.children[0];
      updated = [...updated, child.id];
      node = child;
    }
    setOverrideState({ forValue: value, selections: updated });

    // If the deepest selected node is a leaf (no children), fire onChange
    const deepest = nodesById.get(updated[updated.length - 1]);
    if (deepest && (!deepest.children || deepest.children.length === 0)) {
      const chain = updated
        .map((id) => nodesById.get(id))
        .filter(Boolean) as GeographicAreaNode[];
      onChange(deepest.id, chain);
    }
  };

  const orderedLevels =
    showCountryLast && levels.length > 1
      ? [...levels.slice(1), levels[0]]
      : levels;

  const errorId = errorMessage
    ? `area-select-error-${value || 'new'}`
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
        {orderedLevels.map(function renderLevel(level) {
          const isLevelDisabled =
            disabled ||
            (level.index > 0 && !selections[level.index - 1]) ||
            (level.isCountry && disableCountry);
          return (
            <div key={`${level.label}-${level.index}`}>
              <Label htmlFor={`area-level-${level.index}`}>
                {level.label}
                {required ? <RequiredMark /> : null}
              </Label>
              <Select
                id={`area-level-${level.index}`}
                value={selections[level.index] || ''}
                onChange={(e) => handleSelect(level.index, e.target.value)}
                disabled={isLevelDisabled}
                className={selectClasses}
                aria-invalid={hasError || undefined}
                aria-describedby={errorId}
              >
                {level.options.length === 1 ? null : (
                  <option value=''>
                    Select {level.label.toLowerCase()}
                  </option>
                )}
                {level.options.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                  </option>
                ))}
              </Select>
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
