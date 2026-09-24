'use client';

import { useCallback, useMemo, useRef, useState } from 'react';

import { useActivitiesByMode } from '../../hooks/use-activities-by-mode';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useLocationsByMode } from '../../hooks/use-locations-by-mode';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { parseOptionalNumber } from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import type { LanguageCode } from '../../lib/translations';
import { languageOptions } from '../../lib/translations';
import type { ActivitySchedule } from '../../types/admin';
import { StatusBanner } from '../status-banner';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminDisclosure } from '../ui/admin-disclosure';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Select } from '../ui/select';
import {
  dayOfWeekOptions,
  emptyForm,
  formatTimeLabelForMinutes,
  fromUtcWeekly,
  getLanguageOption,
  getTimeOptions,
  itemToForm,
  toUtcWeekly,
  type ScheduleFormState,
  type WeeklyEntryForm,
} from './schedules/schedule-form-utils';

const minutesPerDay = 24 * 60;
const defaultStartMinutes = 10 * 60;
const defaultDurationMinutes = 60;
const defaultEndMinutes =
  (defaultStartMinutes + defaultDurationMinutes) % minutesPerDay;

function addMinutes(baseMinutes: number, extraMinutes: number): number {
  const total = baseMinutes + extraMinutes;
  return ((total % minutesPerDay) + minutesPerDay) % minutesPerDay;
}

function applyCreateDefaults(
  form: ScheduleFormState,
  editingId: string | null,
  singleActivityId: string,
  singleLocationId: string
): ScheduleFormState {
  if (editingId) {
    return form;
  }
  const activityId = form.activity_id || singleActivityId;
  const locationId = form.location_id || singleLocationId;
  if (activityId === form.activity_id && locationId === form.location_id) {
    return form;
  }
  return {
    ...form,
    activity_id: activityId,
    location_id: locationId,
  };
}

interface SchedulesPanelProps {
  mode: ApiMode;
}

export function SchedulesPanel({ mode }: SchedulesPanelProps) {
  const panel = useResourceEditor<ActivitySchedule, ScheduleFormState>({
    resource: 'schedules',
    mode,
    emptyForm,
    itemToForm,
    paramName: 'schedule',
    noun: 'schedule',
  });

  const { items: activities } = useActivitiesByMode(mode, { limit: 200 });
  const { items: locations } = useLocationsByMode(mode, { limit: 200 });
  const entryIdRef = useRef(0);

  const [searchQuery, setSearchQuery] = useState('');

  const singleActivityId =
    activities.length === 1 ? (activities[0]?.id ?? '') : '';
  const singleLocationId =
    locations.length === 1 ? (locations[0]?.id ?? '') : '';
  const formState = useMemo(
    () =>
      applyCreateDefaults(
        panel.formState,
        panel.editingId,
        singleActivityId,
        singleLocationId
      ),
    [panel.editingId, panel.formState, singleActivityId, singleLocationId]
  );

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['location_id', 'activity_id', 'days', 'languages'],
    formKey
  );
  const requiredIndicator = validation.requiredIndicator;
  const errorInputClassName =
    'border-red-500 focus:border-red-500 focus:ring-red-500';
  const { markTouched } = validation;

  const validate = () => {
    if (!formState.activity_id || !formState.location_id) {
      return 'Activity and location are required.';
    }
    if (formState.weekly_entries.length === 0) {
      return 'Select at least one day and timeslot.';
    }
    for (const entry of formState.weekly_entries) {
      const dayOfWeek = parseOptionalNumber(entry.day_of_week_local);
      const startMinutes = parseOptionalNumber(entry.start_minutes_local);
      const endMinutes = parseOptionalNumber(entry.end_minutes_local);
      if (dayOfWeek === null || startMinutes === null || endMinutes === null) {
        return 'Each timeslot needs a day and time range.';
      }
      if (startMinutes === endMinutes) {
        return 'Timeslots need a non-zero time range.';
      }
    }
    if (formState.languages.length === 0) {
      return 'Select at least one language.';
    }
    return null;
  };

  const locationError = formState.location_id ? '' : 'Select a location.';
  const activityError = formState.activity_id ? '' : 'Select an activity.';
  const daysError =
    formState.weekly_entries.length > 0 ? '' : 'Select at least one day.';
  const languagesError =
    formState.languages.length > 0 ? '' : 'Select at least one language.';

  const entryErrors = useMemo(() => {
    const errors: Record<
      string,
      { start: string; end: string; range: string }
    > = {};
    for (const entry of formState.weekly_entries) {
      const startMinutes = parseOptionalNumber(entry.start_minutes_local);
      const endMinutes = parseOptionalNumber(entry.end_minutes_local);
      let startError = '';
      let endError = '';
      let rangeError = '';
      if (startMinutes === null) {
        startError = 'Select a start time.';
      }
      if (endMinutes === null) {
        endError = 'Select an end time.';
      }
      if (
        startMinutes !== null &&
        endMinutes !== null &&
        startMinutes === endMinutes
      ) {
        rangeError = 'Timeslots need a non-zero time range.';
      }
      errors[entry.id] = {
        start: startError,
        end: endError,
        range: rangeError,
      };
    }
    return errors;
  }, [formState.weekly_entries]);

  const formToPayload = (form: ScheduleFormState) => {
    const resolved = applyCreateDefaults(
      form,
      panel.editingId,
      singleActivityId,
      singleLocationId
    );
    const weeklyEntries = resolved.weekly_entries
      .map((entry) => {
        const dayOfWeek = parseOptionalNumber(entry.day_of_week_local);
        const startMinutes = parseOptionalNumber(entry.start_minutes_local);
        const endMinutes = parseOptionalNumber(entry.end_minutes_local);
        if (
          dayOfWeek === null ||
          startMinutes === null ||
          endMinutes === null
        ) {
          return null;
        }
        const utcSchedule = toUtcWeekly(dayOfWeek, startMinutes, endMinutes);
        return {
          day_of_week_utc: utcSchedule.dayOfWeek,
          start_minutes_utc: utcSchedule.startMinutes,
          end_minutes_utc: utcSchedule.endMinutes,
        };
      })
      .filter(
        (entry): entry is {
          day_of_week_utc: number;
          start_minutes_utc: number;
          end_minutes_utc: number;
        } => entry !== null
      );

    return {
      activity_id: resolved.activity_id,
      location_id: resolved.location_id,
      schedule_type: 'weekly',
      weekly_entries: weeklyEntries,
      languages: resolved.languages,
    };
  };

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  const selectedLanguages = new Set(formState.languages);
  const selectedDays = new Set(
    formState.weekly_entries.map((entry) => entry.day_of_week_local)
  );

  const entriesByDay = dayOfWeekOptions.map((option) => {
    const entries = formState.weekly_entries
      .filter((entry) => entry.day_of_week_local === option.value)
      .sort((left, right) => {
        const leftStart = parseOptionalNumber(left.start_minutes_local) ?? 0;
        const rightStart = parseOptionalNumber(right.start_minutes_local) ?? 0;
        return leftStart - rightStart;
      });
    return { ...option, entries };
  });

  const nextEntryId = (dayOfWeek: string) => {
    const nextId = entryIdRef.current;
    entryIdRef.current += 1;
    return `entry-${dayOfWeek}-${nextId}`;
  };

  const createEntry = (dayOfWeek: string): WeeklyEntryForm => ({
    id: nextEntryId(dayOfWeek),
    day_of_week_local: dayOfWeek,
    start_minutes_local: `${defaultStartMinutes}`,
    end_minutes_local: `${defaultEndMinutes}`,
  });

  const toggleDay = (dayOfWeek: string) => {
    markTouched('days');
    panel.setFormState((prev) => {
      const hasDay = prev.weekly_entries.some(
        (entry) => entry.day_of_week_local === dayOfWeek
      );
      if (hasDay) {
        return {
          ...prev,
          weekly_entries: prev.weekly_entries.filter(
            (entry) => entry.day_of_week_local !== dayOfWeek
          ),
        };
      }
      return {
        ...prev,
        weekly_entries: [...prev.weekly_entries, createEntry(dayOfWeek)],
      };
    });
  };

  const addTimeslot = (dayOfWeek: string) => {
    panel.setFormState((prev) => ({
      ...prev,
      weekly_entries: [...prev.weekly_entries, createEntry(dayOfWeek)],
    }));
  };

  const updateEntry = (entryId: string, updates: Partial<WeeklyEntryForm>) => {
    panel.setFormState((prev) => ({
      ...prev,
      weekly_entries: prev.weekly_entries.map((entry) =>
        entry.id === entryId ? { ...entry, ...updates } : entry
      ),
    }));
  };

  const updateEntryStartTime = (entryId: string, value: string) => {
    markTouched(`entry-${entryId}-start`);
    const startMinutes = parseOptionalNumber(value);
    if (startMinutes === null) {
      updateEntry(entryId, {
        start_minutes_local: value,
        end_minutes_local: '',
      });
      return;
    }
    const endMinutes = addMinutes(startMinutes, defaultDurationMinutes);
    updateEntry(entryId, {
      start_minutes_local: value,
      end_minutes_local: `${endMinutes}`,
    });
  };

  const removeEntry = (entryId: string) => {
    panel.setFormState((prev) => ({
      ...prev,
      weekly_entries: prev.weekly_entries.filter(
        (entry) => entry.id !== entryId
      ),
    }));
  };

  const getActivityName = useCallback(
    (activityId: string) =>
      activities.find((activity) => activity.id === activityId)?.name ??
      activityId,
    [activities]
  );

  const getLocationName = useCallback(
    (locationId: string) =>
      locations.find((location) => location.id === locationId)?.address ??
      locationId,
    [locations]
  );

  function toggleLanguage(code: LanguageCode) {
    markTouched('languages');
    panel.setFormState((prev) => {
      const isSelected = prev.languages.includes(code);
      const nextLanguages = isSelected
        ? prev.languages.filter((language) => language !== code)
        : [...prev.languages, code];
      return { ...prev, languages: nextLanguages };
    });
  }

  const getLocalEntries = useCallback((item: ActivitySchedule) => {
    const entries = item.weekly_entries ?? [];
    return entries
      .map((entry) => {
        const localSchedule = fromUtcWeekly(
          entry.day_of_week_utc,
          entry.start_minutes_utc,
          entry.end_minutes_utc
        );
        return {
          dayOfWeek: localSchedule.dayOfWeek,
          startMinutes: localSchedule.startMinutes,
          endMinutes: localSchedule.endMinutes,
        };
      })
      .sort((left, right) => {
        if (left.dayOfWeek !== right.dayOfWeek) {
          return left.dayOfWeek - right.dayOfWeek;
        }
        if (left.startMinutes !== right.startMinutes) {
          return left.startMinutes - right.startMinutes;
        }
        return left.endMinutes - right.endMinutes;
      });
  }, []);

  const getDayLabel = useCallback(
    (dayOfWeek: number) =>
      dayOfWeekOptions.find((option) => Number(option.value) === dayOfWeek)
        ?.label ?? `Day ${dayOfWeek}`,
    []
  );

  const renderWeeklyEntries = useCallback(
    (item: ActivitySchedule) => {
      const localEntries = getLocalEntries(item);
      if (localEntries.length === 0) {
        return <span>—</span>;
      }
      return (
        <div className='space-y-1 text-slate-600'>
          {localEntries.map((entry) => (
            <div
              key={`${entry.dayOfWeek}-${entry.startMinutes}-${entry.endMinutes}`}
            >
              <span className='font-medium text-slate-700'>
                {getDayLabel(entry.dayOfWeek)}
              </span>{' '}
              {formatTimeLabelForMinutes(entry.startMinutes)}-
              {formatTimeLabelForMinutes(entry.endMinutes)}
            </div>
          ))}
        </div>
      );
    },
    [getDayLabel, getLocalEntries]
  );

  const weeklyEntriesLabel = useCallback(
    (item: ActivitySchedule) => {
      const localEntries = getLocalEntries(item);
      return localEntries
        .map((entry) => {
          const label = getDayLabel(entry.dayOfWeek);
          const start = formatTimeLabelForMinutes(entry.startMinutes);
          const end = formatTimeLabelForMinutes(entry.endMinutes);
          return `${label} ${start}-${end}`;
        })
        .join(', ');
    },
    [getDayLabel, getLocalEntries]
  );

  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const activityName = getActivityName(item.activity_id).toLowerCase();
    const locationName = getLocationName(item.location_id).toLowerCase();
    const languagesStr = item.languages?.join(', ')?.toLowerCase() || '';
    const entriesLabel = weeklyEntriesLabel(item).toLowerCase();
    return (
      activityName.includes(query) ||
      locationName.includes(query) ||
      entriesLabel.includes(query) ||
      languagesStr.includes(query)
    );
  });

  const showLocationError = validation.shouldShowError(
    'location_id',
    Boolean(locationError)
  );
  const showActivityError = validation.shouldShowError(
    'activity_id',
    Boolean(activityError)
  );
  const showDaysError = validation.shouldShowError('days', Boolean(daysError));
  const showLanguagesError = validation.shouldShowError(
    'languages',
    Boolean(languagesError)
  );

  const detail = (
    <AdminEditorPanel
      status={
        panel.error ? (
          <StatusBanner variant='error' title='Error'>
            {panel.error}
          </StatusBanner>
        ) : null
      }
      actions={
        <AdminEditorActions
          mode={panel.editorMode}
          onSubmit={handleSubmit}
          isSaving={panel.isSaving}
        />
      }
    >
      <AdminFieldGrid columns={2}>
        <div className='space-y-1'>
          <Label htmlFor='schedule-location'>
            Location <span className='ml-1'>{requiredIndicator}</span>
          </Label>
          <Select
            id='schedule-location'
            value={formState.location_id}
            onChange={(e) => {
              markTouched('location_id');
              panel.setFormState((prev) => ({
                ...prev,
                location_id: e.target.value,
              }));
            }}
            className={showLocationError ? errorInputClassName : ''}
            aria-invalid={showLocationError || undefined}
          >
            <option value=''>Select location</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.address || location.area_id}
              </option>
            ))}
          </Select>
          {showLocationError ? (
            <p className='text-xs text-red-600'>{locationError}</p>
          ) : null}
        </div>
        <div className='space-y-1'>
          <Label htmlFor='schedule-activity'>
            Activity <span className='ml-1'>{requiredIndicator}</span>
          </Label>
          <Select
            id='schedule-activity'
            value={formState.activity_id}
            onChange={(e) => {
              markTouched('activity_id');
              panel.setFormState((prev) => ({
                ...prev,
                activity_id: e.target.value,
              }));
            }}
            className={showActivityError ? errorInputClassName : ''}
            aria-invalid={showActivityError || undefined}
          >
            <option value=''>Select activity</option>
            {activities.map((activity) => (
              <option key={activity.id} value={activity.id}>
                {activity.name}
              </option>
            ))}
          </Select>
          {showActivityError ? (
            <p className='text-xs text-red-600'>{activityError}</p>
          ) : null}
        </div>
        <div className='sm:col-span-2'>
          <AdminDisclosure
            id='schedule-weekly'
            title='Weekly schedule'
            defaultOpen
            summary={
              selectedDays.size > 0
                ? `${selectedDays.size} day${selectedDays.size === 1 ? '' : 's'}`
                : 'No days selected'
            }
          >
            <div className='space-y-4'>
              <div className='space-y-2'>
                <Label id='schedule-days-label'>
                  Days of Week <span className='ml-1'>{requiredIndicator}</span>
                </Label>
                <p id='schedule-days-help' className='text-xs text-slate-500'>
                  Select one or more days, then add timeslots.
                </p>
                <div
                  role='group'
                  aria-labelledby='schedule-days-label'
                  aria-describedby='schedule-days-help'
                  className={`flex flex-wrap items-center gap-2 ${
                    showDaysError ? 'ring-1 ring-red-500 rounded-md p-2' : ''
                  }`}
                >
                  {dayOfWeekOptions.map((option) => {
                    const isSelected = selectedDays.has(option.value);
                    return (
                      <button
                        key={option.value}
                        type='button'
                        onClick={() => toggleDay(option.value)}
                        className={`rounded border px-2 py-1 text-sm transition ${
                          isSelected
                            ? 'border-slate-400 bg-slate-50 ring-2 ring-slate-200'
                            : 'border-slate-200 hover:border-slate-300'
                        }`}
                        aria-pressed={isSelected}
                      >
                        {option.label.slice(0, 3)}
                      </button>
                    );
                  })}
                </div>
                {showDaysError ? (
                  <p className='text-xs text-red-600'>{daysError}</p>
                ) : null}
              </div>
              {entriesByDay
                .filter((day) => day.entries.length > 0)
                .map((day) => (
                  <div key={day.value}>
                    <div className='space-y-3 rounded border border-slate-200 bg-slate-50 p-4'>
                      <div className='flex flex-wrap items-center justify-between gap-2'>
                        <div>
                          <p className='text-sm font-semibold text-slate-900'>
                            {day.label}
                          </p>
                          <p className='text-xs text-slate-500'>
                            Add one or more timeslots.
                          </p>
                        </div>
                        <Button
                          type='button'
                          size='sm'
                          variant='ghost'
                          onClick={() => toggleDay(day.value)}
                        >
                          Remove day
                        </Button>
                      </div>
                      <div className='space-y-3'>
                        {day.entries.map((entry) => {
                          const startId = `schedule-${day.value}-${entry.id}-start`;
                          const endId = `schedule-${day.value}-${entry.id}-end`;
                          const startTouchedKey = `entry-${entry.id}-start`;
                          const endTouchedKey = `entry-${entry.id}-end`;
                          const startOptions = getTimeOptions(
                            entry.start_minutes_local
                          );
                          const endOptions = getTimeOptions(entry.end_minutes_local);
                          const entryError = entryErrors[entry.id] ?? {
                            start: '',
                            end: '',
                            range: '',
                          };
                          const showStartError = Boolean(
                            entryError.start &&
                              (validation.hasSubmitted ||
                                validation.touched[startTouchedKey])
                          );
                          const showEndError = Boolean(
                            entryError.end &&
                              (validation.hasSubmitted ||
                                validation.touched[endTouchedKey])
                          );
                          const showRangeError = Boolean(
                            entryError.range &&
                              (validation.hasSubmitted ||
                                validation.touched[startTouchedKey] ||
                                validation.touched[endTouchedKey])
                          );
                          return (
                            <div
                              key={entry.id}
                              className='grid gap-3 md:grid-cols-[1fr_1fr_auto]'
                            >
                              <div>
                                <Label htmlFor={startId}>
                                  Start Time (Local){' '}
                                  <span className='ml-1'>{requiredIndicator}</span>
                                </Label>
                                <Select
                                  id={startId}
                                  value={entry.start_minutes_local}
                                  onChange={(e) =>
                                    updateEntryStartTime(entry.id, e.target.value)
                                  }
                                  className={
                                    showStartError || showRangeError
                                      ? errorInputClassName
                                      : ''
                                  }
                                  aria-invalid={
                                    showStartError || showRangeError || undefined
                                  }
                                >
                                  <option value=''>Select time</option>
                                  {startOptions.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </Select>
                                {showStartError ? (
                                  <p className='text-xs text-red-600'>
                                    {entryError.start}
                                  </p>
                                ) : null}
                              </div>
                              <div>
                                <Label htmlFor={endId}>
                                  End Time (Local){' '}
                                  <span className='ml-1'>{requiredIndicator}</span>
                                </Label>
                                <Select
                                  id={endId}
                                  value={entry.end_minutes_local}
                                  onChange={(e) => {
                                    markTouched(endTouchedKey);
                                    updateEntry(entry.id, {
                                      end_minutes_local: e.target.value,
                                    });
                                  }}
                                  className={
                                    showEndError || showRangeError
                                      ? errorInputClassName
                                      : ''
                                  }
                                  aria-invalid={
                                    showEndError || showRangeError || undefined
                                  }
                                >
                                  <option value=''>Select time</option>
                                  {endOptions.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </Select>
                                {showEndError ? (
                                  <p className='text-xs text-red-600'>
                                    {entryError.end}
                                  </p>
                                ) : showRangeError ? (
                                  <p className='text-xs text-red-600'>
                                    {entryError.range}
                                  </p>
                                ) : null}
                              </div>
                              <div className='flex items-end'>
                                <Button
                                  type='button'
                                  size='sm'
                                  variant='ghost'
                                  onClick={() => removeEntry(entry.id)}
                                >
                                  Remove
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <div>
                        <Button
                          type='button'
                          size='sm'
                          variant='secondary'
                          onClick={() => addTimeslot(day.value)}
                        >
                          Add timeslot
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </AdminDisclosure>
        </div>
        <div className='sm:col-span-2'>
          <div className='space-y-2'>
            <Label id='schedule-languages-label'>
              Languages <span className='ml-1'>{requiredIndicator}</span>
            </Label>
            <p id='schedule-languages-help' className='text-xs text-slate-500'>
              Select one or more flags.
            </p>
            <div
              role='group'
              aria-labelledby='schedule-languages-label'
              aria-describedby='schedule-languages-help'
              className={`flex flex-wrap items-center gap-2 ${
                showLanguagesError ? 'ring-1 ring-red-500 rounded-md p-2' : ''
              }`}
            >
              {languageOptions.map((option) => {
                const isSelected = selectedLanguages.has(option.code);
                return (
                  <button
                    key={option.code}
                    type='button'
                    onClick={() => toggleLanguage(option.code)}
                    className={`relative flex items-center justify-center rounded border px-2 py-1 transition ${
                      isSelected
                        ? 'border-slate-400 bg-slate-50 ring-2 ring-slate-200'
                        : 'border-slate-200 hover:border-slate-300'
                    }`}
                    aria-pressed={isSelected}
                    aria-label={`Toggle ${option.label}`}
                    title={option.label}
                  >
                    <img
                      src={option.flagSrc}
                      alt={`${option.label} flag`}
                      width={40}
                      height={28}
                      loading='lazy'
                    />
                  </button>
                );
              })}
            </div>
            {showLanguagesError ? (
              <p className='text-xs text-red-600'>{languagesError}</p>
            ) : null}
          </div>
        </div>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <>
      <ResourceTableShell
        ariaLabel='Schedules'
        rows={filteredItems}
        getLabel={(item) => getLocationName(item.location_id)}
        middleColumnCount={4}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No schedules match your search.'
            : 'No schedules yet.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New schedule'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New schedule'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField label='Search' htmlFor='schedule-search'>
              <Input
                id='schedule-search'
                placeholder='Search schedules...'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Location</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Activity
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Day/Time
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Languages
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              {getLocationName(item.location_id)}
              <AdminDataTableCellMeta until='secondary'>
                {weeklyEntriesLabel(item) || '—'}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {getActivityName(item.activity_id)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {renderWeeklyEntries(item)}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <div className='flex flex-wrap items-center gap-2 text-slate-600'>
                {item.languages?.length ? (
                  item.languages.map((language) => {
                    const option = getLanguageOption(language);
                    if (!option) {
                      return (
                        <span key={language} className='text-xs uppercase'>
                          {language}
                        </span>
                      );
                    }
                    return (
                      <span
                        key={option.code}
                        className='inline-flex items-center justify-center rounded border border-slate-200 bg-white px-1.5 py-1'
                        title={option.label}
                      >
                        <img
                          src={option.flagSrc}
                          alt={`${option.label} flag`}
                          width={20}
                          height={14}
                          loading='lazy'
                        />
                      </span>
                    );
                  })
                ) : (
                  <span>—</span>
                )}
              </div>
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          deleteRowActions(() =>
            panel.handleDelete({
              ...item,
              name: getActivityName(item.activity_id),
            })
          )
        }
      />
      {panel.confirmDialog}
    </>
  );
}
