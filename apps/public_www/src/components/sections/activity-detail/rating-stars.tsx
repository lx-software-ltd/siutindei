const STAR_COUNT = 5;

/** Decorative stars; the number is always also given as text nearby. */
export function RatingStars({
  stars,
  className = 'h-4 w-4',
}: {
  readonly stars: number;
  readonly className?: string;
}) {
  const filled = Math.round(stars);
  return (
    <span className="inline-flex gap-0.5" aria-hidden="true">
      {Array.from({ length: STAR_COUNT }, (_, index) => (
        <img
          key={index}
          src={index < filled ? '/images/icons/star.svg' : '/images/icons/star-empty.svg'}
          alt=""
          width={16}
          height={16}
          className={className}
        />
      ))}
    </span>
  );
}
