'use client';

interface SearchViewToggleProps {
  readonly isMapView: boolean;
  readonly groupLabel: string;
  readonly listLabel: string;
  readonly mapLabel: string;
  readonly onShowList: () => void;
  readonly onShowMap: () => void;
}

const LIST_ICON_SRC = '/images/ui/list.svg';
const MAP_ICON_SRC = '/images/ui/map.svg';

function segmentClassName(isActive: boolean): string {
  return (
    'inline-flex min-h-11 items-center gap-2 rounded-full px-4 text-sm font-semibold transition ' +
    (isActive ? 'bg-ink-900 text-white' : 'text-ink-700 hover:bg-brand-50')
  );
}

/** List and Map as one segmented control, so the current view is always visible. */
export function SearchViewToggle({
  isMapView,
  groupLabel,
  listLabel,
  mapLabel,
  onShowList,
  onShowMap,
}: SearchViewToggleProps) {
  return (
    <div
      role="group"
      aria-label={groupLabel}
      className="search-view-toggle inline-flex shrink-0 rounded-full border border-ink-900/15 bg-white p-0.5"
    >
      <button
        type="button"
        aria-pressed={!isMapView}
        onClick={isMapView ? onShowList : undefined}
        className={segmentClassName(!isMapView)}
      >
        <img
          src={LIST_ICON_SRC}
          alt=""
          width={16}
          height={16}
          decoding="async"
          aria-hidden="true"
          className={`h-4 w-4 ${isMapView ? '' : 'invert'}`}
        />
        {listLabel}
      </button>
      <button
        type="button"
        aria-pressed={isMapView}
        onClick={isMapView ? undefined : onShowMap}
        className={segmentClassName(isMapView)}
      >
        <img
          src={MAP_ICON_SRC}
          alt=""
          width={16}
          height={16}
          decoding="async"
          aria-hidden="true"
          className={`h-4 w-4 ${isMapView ? 'invert' : ''}`}
        />
        {mapLabel}
      </button>
    </div>
  );
}
