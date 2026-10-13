import { Children, type ReactNode } from 'react';

/** True when `node` renders something other than null, false, or whitespace. */
export function hasContent(node: ReactNode): boolean {
  return Children.toArray(node).some((child) => {
    if (typeof child === 'string') {
      return child.trim().length > 0;
    }
    return child != null && typeof child !== 'boolean';
  });
}
