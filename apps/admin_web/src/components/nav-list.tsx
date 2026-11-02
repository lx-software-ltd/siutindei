'use client';

export interface NavSection {
  key: string;
  label: string;
  dividerBefore?: boolean;
}

export function NavList({
  sections,
  activeKey,
  onSelect,
  onIntent,
  itemClassName,
}: {
  sections: NavSection[];
  activeKey: string;
  onSelect: (key: string) => void;
  onIntent?: (key: string) => void;
  itemClassName: (isActive: boolean) => string;
}) {
  return (
    <>
      {sections.map((section) => {
        const isActive = section.key === activeKey;
        return (
          <div key={section.key}>
            {section.dividerBefore ? <hr className='my-3 border-brand-100' /> : null}
            <button
              type='button'
              onClick={() => onSelect(section.key)}
              onMouseEnter={() => onIntent?.(section.key)}
              onFocus={() => onIntent?.(section.key)}
              className={itemClassName(isActive)}
            >
              {section.label}
            </button>
          </div>
        );
      })}
    </>
  );
}
