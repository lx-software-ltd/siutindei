import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ActivityGallery } from '@/components/sections/activity-detail/activity-gallery';
import { getContent } from '@/content';

const copy = getContent('en').activityDetail;
const PHOTOS = [
  'https://images.example.com/tall.jpg',
  'https://images.example.com/wide.jpg',
  'https://images.example.com/square.jpg',
];

describe('ActivityGallery', () => {
  it('covers each tile and contains the opened photo', () => {
    const { container } = render(
      <ActivityGallery
        title="Kowloon art"
        imageUrls={PHOTOS}
        isLogo={false}
        fallbackIconSrc="/images/icons/arts.svg"
        copy={copy}
      />,
    );

    const covered = container.querySelectorAll('img.object-cover');
    expect(covered.length).toBeGreaterThanOrEqual(PHOTOS.length);
    for (const img of covered) {
      expect(img).toHaveClass('absolute', 'inset-0', 'h-full', 'w-full', 'object-cover');
    }
    expect(container.querySelector('button.min-h-0')).not.toBeNull();

    fireEvent.click(screen.getAllByRole('button', { name: 'Kowloon art' })[0]);
    const opened = document.querySelector(
      'img[src="https://images.example.com/tall.jpg"].object-contain',
    );
    expect(opened).toHaveClass('max-h-[70vh]', 'w-full', 'object-contain');
  });
});
