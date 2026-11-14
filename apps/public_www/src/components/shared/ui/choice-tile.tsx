type ChoiceTileSize = 'default' | 'compact';

interface ChoiceTileProps {
  readonly label: string;
  readonly iconSrc: string;
  readonly isSelected: boolean;
  readonly onClick: () => void;
  readonly iconShape?: 'illustration' | 'flag';
  readonly size?: ChoiceTileSize;
  readonly disabled?: boolean;
  readonly disabledHint?: string;
  readonly hint?: string;
}

const TILE_SIZE_CLASS: Record<
  ChoiceTileSize,
  { container: string; icon: string; iconPx: number }
> = {
  default: {
    container: 'gap-2 px-2 pb-3 pt-4 sm:gap-3 sm:px-4 sm:pb-5 sm:pt-6',
    icon: 'h-14 w-14 sm:h-24 sm:w-24',
    iconPx: 96,
  },
  compact: {
    container:
      'gap-2 px-2 pb-3 pt-4 sm:gap-[0.6rem] sm:px-4 sm:pb-4 sm:pt-[1.2rem]',
    icon: 'h-14 w-14 sm:h-[4.8rem] sm:w-[4.8rem]',
    iconPx: 77,
  },
};

export function ChoiceTile({
  label,
  iconSrc,
  isSelected,
  onClick,
  iconShape = 'illustration',
  size = 'default',
  disabled = false,
  disabledHint,
  hint,
}: ChoiceTileProps) {
  const selectedClassName = disabled
    ? 'cursor-not-allowed border-brand-100 bg-white opacity-40'
    : isSelected
      ? 'border-accent-500 bg-brand-50 ' +
        'shadow-[0_10px_30px_rgba(29,64,59,0.12)]'
      : 'border-brand-100 bg-white hover:border-brand-200 ' +
        'hover:shadow-[0_10px_30px_rgba(29,64,59,0.1)]';
  const sizeClassName = TILE_SIZE_CLASS[size];
  const iconClassName =
    iconShape === 'flag'
      ? `${sizeClassName.icon} rounded-full object-cover ring-1 ring-ink-900/15`
      : `${sizeClassName.icon} object-contain`;

  return (
    <button
      type="button"
      aria-pressed={disabled ? undefined : isSelected}
      aria-disabled={disabled || undefined}
      onClick={disabled ? undefined : onClick}
      className={
        'choice-tile group flex flex-col items-center ' +
        `rounded-2xl border transition ${sizeClassName.container} ` +
        selectedClassName
      }
    >
      <img
        src={iconSrc}
        alt=""
        width={sizeClassName.iconPx}
        height={sizeClassName.iconPx}
        decoding="async"
        aria-hidden="true"
        className={`choice-tile__icon ${iconClassName}`}
      />
      <span
        className={`text-sm font-semibold ${
          isSelected ? 'text-brand-700' : 'text-ink-900'
        }`}
      >
        {label}
      </span>
      {disabled && disabledHint ? (
        <span className="text-xs font-medium text-ink-500">{disabledHint}</span>
      ) : hint ? (
        <span className="text-center text-xs font-medium text-ink-500">{hint}</span>
      ) : null}
    </button>
  );
}
