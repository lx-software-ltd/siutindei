type ChoiceLayout = 'fill' | 'chip';
type IconShape = 'illustration' | 'flag';

interface SearchChoiceButtonProps {
  readonly label: string;
  readonly iconSrc: string;
  readonly isSelected: boolean;
  readonly onClick: () => void;
  readonly className?: string;
  readonly iconShape?: IconShape;
  readonly disabled?: boolean;
  readonly disabledHint?: string;
  readonly layout?: ChoiceLayout;
}

interface ChoicePresentation {
  readonly frame: string;
  readonly iconSlot: string;
  readonly icon: string;
  readonly iconPx: number;
  readonly label: string;
}

const FILL_FRAME =
  'md:min-w-0 md:w-full md:flex-1 md:flex-col md:items-center ' +
  'md:justify-start md:gap-2 md:self-stretch md:rounded-2xl md:px-2 md:py-3';

const CHIP_FRAME =
  'md:h-[50px] md:w-full md:min-w-0 md:flex-row md:justify-start ' +
  'md:gap-2 md:overflow-hidden md:rounded-xl md:px-2.5 md:py-0';

function choicePresentation(
  layout: ChoiceLayout,
  iconShape: IconShape,
): ChoicePresentation {
  if (iconShape === 'flag') {
    return {
      frame: FILL_FRAME,
      iconSlot: 'h-12 w-12',
      icon: 'h-10 w-10 rounded-full object-cover ring-1 ring-ink-900/15',
      iconPx: 40,
      label: 'md:text-center',
    };
  }
  if (layout === 'chip') {
    return {
      frame: CHIP_FRAME,
      iconSlot: 'md:h-[30px] md:w-[30px]',
      icon: 'h-[30px] w-[30px] object-contain',
      iconPx: 30,
      label:
        'min-w-0 text-left md:line-clamp-2 md:text-balance md:text-[13px] md:leading-4',
    };
  }
  return {
    frame: FILL_FRAME,
    iconSlot: 'h-12 w-12',
    icon: 'h-12 w-12 object-contain',
    iconPx: 48,
    label: 'md:text-center',
  };
}

function selectionClassName(disabled: boolean, isSelected: boolean): string {
  if (disabled) {
    return 'cursor-not-allowed border-ink-900/15 bg-white text-ink-500 opacity-40';
  }
  if (isSelected) {
    return (
      'border-ink-900 bg-ink-900 text-white ' +
      'md:border-accent-500 md:bg-brand-50 md:text-brand-700'
    );
  }
  return (
    'border-ink-900/15 bg-white text-ink-700 ' +
    'hover:border-ink-900/30 md:hover:border-brand-200'
  );
}

export function SearchChoiceButton({
  label,
  iconSrc,
  isSelected,
  onClick,
  className = '',
  iconShape = 'illustration',
  disabled = false,
  disabledHint,
  layout = 'fill',
}: SearchChoiceButtonProps) {
  const presentation = choicePresentation(layout, iconShape);

  return (
    <button
      type="button"
      aria-pressed={disabled ? undefined : isSelected}
      aria-disabled={disabled || undefined}
      onClick={disabled ? undefined : onClick}
      className={
        'search-choice inline-flex shrink-0 items-center gap-2 ' +
        'rounded-full border px-4 py-2 text-sm font-medium leading-5 ' +
        `transition ${presentation.frame} ${selectionClassName(disabled, isSelected)} ${className}`
      }
    >
      <span
        className={
          'search-choice-icon hidden shrink-0 items-center justify-center md:flex ' +
          presentation.iconSlot
        }
      >
        <img
          src={iconSrc}
          alt=""
          width={presentation.iconPx}
          height={presentation.iconPx}
          decoding="async"
          aria-hidden="true"
          className={presentation.icon}
        />
      </span>
      <span className={presentation.label}>
        {label}
        {disabled && disabledHint ? (
          <span className="mt-1 block text-xs font-medium">{disabledHint}</span>
        ) : null}
      </span>
    </button>
  );
}
