import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { Carousel } from '@/components/shared/ui/carousel';

describe('Carousel', () => {
  it('renders a scrollable track without prev/next buttons', () => {
    render(
      <Carousel ariaLabel="Popular activities">
        <div>Card</div>
      </Carousel>,
    );

    expect(
      screen.getByRole('region', { name: 'Popular activities' }),
    ).toHaveClass('listing-carousel__track');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText('Card')).toBeInTheDocument();
  });

  describe('with arrow labels', () => {
    const descriptors = ['clientWidth', 'scrollWidth'].map(
      (key) => [key, Object.getOwnPropertyDescriptor(HTMLElement.prototype, key)] as const,
    );

    afterEach(() => {
      for (const [key, descriptor] of descriptors) {
        if (descriptor) {
          Object.defineProperty(HTMLElement.prototype, key, descriptor);
        }
      }
    });

    it('pages forward and back and disables the arrow at each end', () => {
      Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, get: () => 300 });
      Object.defineProperty(HTMLElement.prototype, 'scrollWidth', { configurable: true, get: () => 1000 });
      render(
        <Carousel ariaLabel="Popular activities" previousLabel="Previous" nextLabel="Next">
          <div>Card</div>
        </Carousel>,
      );

      const track = screen.getByRole('region', { name: 'Popular activities' });
      const scrollBy = vi.fn();
      track.scrollBy = scrollBy;
      const previous = screen.getByRole('button', { name: 'Previous' });
      const next = screen.getByRole('button', { name: 'Next' });
      expect(previous).toBeDisabled();
      expect(next).toBeEnabled();

      fireEvent.click(next);
      expect(scrollBy).toHaveBeenCalledWith({ left: 270, behavior: 'smooth' });

      track.scrollLeft = 700;
      fireEvent.scroll(track);
      expect(previous).toBeEnabled();
      expect(next).toBeDisabled();
    });
  });
});
