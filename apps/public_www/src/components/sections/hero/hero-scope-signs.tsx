import {
  heroScopeSignSrc,
  type HeroScopeSign,
} from '@/lib/home-wizard/area-scope';

const TILT = [
  'hero-scope-sign--tilt-a',
  'hero-scope-sign--tilt-b',
  'hero-scope-sign--tilt-c',
] as const;

interface HeroScopeSignsProps {
  readonly signs: readonly HeroScopeSign[];
}

/** Street-name plates for the open places, plus the phone arrow. */
export function HeroScopeSigns({ signs }: HeroScopeSignsProps) {
  if (signs.length === 0) {
    return null;
  }
  const last = signs.length - 1;
  return (
    <div className="hero-scope-signs" aria-hidden="true">
      {signs.map((sign, index) => {
        const tilt = TILT[index] ?? TILT[0];
        const extra = index >= 2 ? 'hero-scope-sign--extra' : '';
        return (
          <img
            key={sign.id}
            src={heroScopeSignSrc(sign.id)}
            alt=""
            decoding="async"
            data-scope-sign-target={index === last ? '' : undefined}
            className={['hero-scope-sign', tilt, extra].filter(Boolean).join(' ')}
          />
        );
      })}
      <img
        src="/images/ui/scope-arrow.svg"
        alt=""
        className="hero-scope-signs__arrow"
      />
    </div>
  );
}
