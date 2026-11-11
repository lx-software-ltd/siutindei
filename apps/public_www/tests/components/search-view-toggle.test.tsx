import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SearchViewToggle } from '@/components/sections/search/search-view-toggle';

function renderToggle(isMapView: boolean) {
  const onShowList = vi.fn();
  const onShowMap = vi.fn();
  render(
    <SearchViewToggle
      isMapView={isMapView}
      groupLabel="Results"
      listLabel="List"
      mapLabel="Map"
      onShowList={onShowList}
      onShowMap={onShowMap}
    />,
  );
  return { onShowList, onShowMap };
}

describe('SearchViewToggle', () => {
  it('marks the list as current and switches to the map', () => {
    const { onShowList, onShowMap } = renderToggle(false);

    expect(screen.getByRole('group', { name: 'Results' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true');
    const map = screen.getByRole('button', { name: 'Map' });
    expect(map).toHaveAttribute('aria-pressed', 'false');
    expect(map.querySelector('img')).toHaveAttribute('src', '/images/ui/map.svg');

    fireEvent.click(map);
    expect(onShowMap).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'List' }));
    expect(onShowList).not.toHaveBeenCalled();
  });

  it('marks the map as current and switches to the list', () => {
    const { onShowList, onShowMap } = renderToggle(true);

    expect(screen.getByRole('button', { name: 'Map' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'List' }));
    expect(onShowList).toHaveBeenCalledOnce();
    expect(onShowMap).not.toHaveBeenCalled();
  });
});
