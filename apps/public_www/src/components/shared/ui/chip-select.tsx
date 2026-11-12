import type { SelectHTMLAttributes } from 'react';

interface ChipSelectOption {
  readonly value: string;
  readonly label: string;
}

interface ChipSelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children' | 'value' | 'onChange'> {
  readonly label: string;
  readonly value: string;
  readonly options: readonly ChipSelectOption[];
  /** The value that means "not filtered"; any other value shows the chip as selected. */
  readonly emptyValue?: string;
  readonly onValueChange: (value: string) => void;
}

/** A native select styled as a filter chip; phones get their own picker. */
export function ChipSelect({
  label,
  value,
  options,
  emptyValue = '',
  onValueChange,
  className = '',
  ...props
}: ChipSelectProps) {
  const isSelected = value !== emptyValue;
  const stateClassName = isSelected
    ? 'border-ink-900 bg-accent-500 text-ink-900'
    : 'border-ink-900/15 bg-white text-ink-700 hover:border-ink-900/30';
  return (
    <span className={`relative inline-flex shrink-0 ${className}`}>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        className={
          'min-h-11 cursor-pointer appearance-none rounded-full border py-2 pl-4 pr-9 ' +
          `text-sm font-medium transition ${stateClassName}`
        }
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <img
        src="/images/ui/chevron-down.svg"
        alt=""
        width={16}
        height={16}
        aria-hidden="true"
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2"
      />
    </span>
  );
}
