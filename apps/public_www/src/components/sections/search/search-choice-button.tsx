/**
 * `fill` is a tile with the icon over the label. `chip` is a row with the
 * icon beside the label. `area` is a row on phones, where a tile per area
 * would not fit one line, and a tile from iPad portrait up.
 */
type ChoiceLayout = 'fill' | 'chip' | 'area';
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

const TILE_FROM_MD =
  'md:min-h-0 md:w-full md:flex-1 md:flex-col md:justify-start md:gap-2 ' +
  'md:self-stretch md:rounded-2xl md:px-2 md:py-3 md:text-center';

const FILL_FRAME =
  'flex-col justify-start gap-1 rounded-xl px-1 py-2 text-center ' +
  TILE_FROM_MD;

const AREA_FRAME =
  `min-h-11 justify-start gap-2 rounded-xl px-2.5 py-1 text-left ${TILE_FROM_MD}`;

const CHIP_FRAME =
  'h-11 w-full justify-start gap-1.5 overflow-hidden rounded-xl px-2 ' +
  'text-left md:h-[50px] md:gap-2 md:px-2.5';

// System fonts differ in width, so a long word breaks instead of spilling out.
const LABEL_WRAP = 'min-w-0 [overflow-wrap:anywhere]';

const TILE_LABEL = `${LABEL_WRAP} text-[13px] leading-4 md:text-sm md:leading-5`;

function tileIcon(layout: ChoiceLayout, iconShape: IconShape) {
  const slot = layout === 'area' ? 'h-8 w-8' : 'h-9 w-9';
  if (iconShape === 'flag') {
    return {
      iconSlot: `${slot} md:h-12 md:w-12`,
      icon: 'h-7 w-7 rounded-full object-cover ring-1 ring-ink-900/15 md:h-10 md:w-10',
      iconPx: 40,
    };
  }
  return {
    iconSlot: `${slot} md:h-12 md:w-12`,
    icon: `${slot} object-contain md:h-12 md:w-12`,
    iconPx: 48,
  };
}

function choicePresentation(
  layout: ChoiceLayout,
  iconShape: IconShape,
): ChoicePresentation {
  if (layout === 'chip') {
    return {
      frame: CHIP_FRAME,
      iconSlot: 'h-[30px] w-[30px]',
      icon: 'h-[30px] w-[30px] object-contain',
      iconPx: 30,
      label: `${LABEL_WRAP} line-clamp-2 text-balance text-[13px] leading-4`,
    };
  }
  return {
    frame: layout === 'area' ? AREA_FRAME : FILL_FRAME,
    ...tileIcon(layout, iconShape),
    label: TILE_LABEL,
  };
}

function selectionClassName(disabled: boolean, isSelected: boolean): string {
  if (disabled) {
    // Phones keep the hint readable and fade only the icon.
    return (
      'cursor-not-allowed border-ink-900/15 bg-white text-ink-500 ' +
      'max-md:border-dashed md:opacity-40'
    );
  }
  if (isSelected) {
    return (
      'border-ink-900 bg-brand-100 font-semibold text-ink-900 ' +
      'md:border-accent-500 md:bg-brand-50 md:font-medium md:text-brand-700'
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
        'search-choice inline-flex min-w-0 items-center border text-sm font-medium ' +
        `leading-5 transition ${presentation.frame} ${selectionClassName(disabled, isSelected)} ${className}`
      }
    >
      <span
        className={
          'search-choice-icon flex shrink-0 items-center justify-center ' +
          `${presentation.iconSlot} ${disabled ? 'max-md:opacity-40' : ''}`
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
          <span className="block text-[11px] font-medium leading-4 md:mt-1 md:text-xs">
            {disabledHint}
          </span>
        ) : null}
      </span>
    </button>
  );
}
