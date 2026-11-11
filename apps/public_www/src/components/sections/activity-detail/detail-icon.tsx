export type DetailIconName =
  | 'age'
  | 'calendar'
  | 'pin'
  | 'price'
  | 'language'
  | 'globe'
  | 'phone'
  | 'mail'
  | 'chat'
  | 'link'
  | 'directions'
  | 'back'
  | 'clock'
  | 'check';

export function DetailIcon({
  name,
  className = 'h-5 w-5',
}: {
  readonly name: DetailIconName;
  readonly className?: string;
}) {
  return (
    <img
      src={`/images/icons/${name}.svg`}
      alt=""
      width={20}
      height={20}
      aria-hidden="true"
      decoding="async"
      className={`shrink-0 ${className}`}
    />
  );
}
