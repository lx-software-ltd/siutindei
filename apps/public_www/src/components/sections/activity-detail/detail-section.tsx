import type { ReactNode } from 'react';

export function DetailSection({
  id,
  title,
  children,
}: {
  readonly id: string;
  readonly title: string;
  readonly children: ReactNode;
}) {
  const headingId = `${id}-heading`;
  return (
    <section
      id={id}
      aria-labelledby={headingId}
      className="scroll-mt-24 border-t border-brand-100 pt-6"
    >
      <h2 id={headingId} className="text-xl font-semibold text-ink-900">
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}
