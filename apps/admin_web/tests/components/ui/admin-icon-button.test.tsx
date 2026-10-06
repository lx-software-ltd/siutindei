import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EditIcon } from '@/components/icons/action-icons';
import { AdminIconButton } from '@/components/ui/admin-icon-button';

describe('AdminIconButton', () => {
  it('sizes a child svg so operations icons are visible', () => {
    render(<AdminIconButton label='Apply' icon={<EditIcon />} />);

    const button = screen.getByRole('button', { name: 'Apply' });
    expect(button.className).toContain('[&>svg]:h-4');
    expect(button.className).toContain('[&>svg]:w-4');
    expect(button.querySelector('svg')).not.toBeNull();
  });
});
