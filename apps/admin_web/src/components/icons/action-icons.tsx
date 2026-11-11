'use client';

interface IconProps {
  className?: string;
}

export function EditIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7' />
      <path d='M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z' />
    </svg>
  );
}

export function MergeIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M8 7H4v13h13v-4' />
      <path d='M16 3h5v5' />
      <path d='M10 14L21 3' />
    </svg>
  );
}

export function DeleteIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <polyline points='3 6 5 6 21 6' />
      <path d='M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' />
      <line x1='10' y1='11' x2='10' y2='17' />
      <line x1='14' y1='11' x2='14' y2='17' />
    </svg>
  );
}

export function ViewIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' />
      <circle cx='12' cy='12' r='3' />
    </svg>
  );
}

export function ReviewIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' />
      <circle cx='12' cy='12' r='3' />
    </svg>
  );
}

export function GoogleIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox='0 0 24 24' fill='currentColor'>
      <path
        d='M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z'
        fill='#4285F4'
      />
      <path
        d='M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z'
        fill='#34A853'
      />
      <path
        d='M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z'
        fill='#FBBC05'
      />
      <path
        d='M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z'
        fill='#EA4335'
      />
    </svg>
  );
}

export function AppleIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox='0 0 24 24' fill='currentColor'>
      <path d='M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z' />
    </svg>
  );
}

export function AppleMapsIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox='2.225 0 19.55 24' aria-hidden='true'>
      <path
        fill='currentColor'
        d='M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04c-2.04.027-3.91 1.183-4.961 3.014c-2.117 3.675-.546 9.103 1.519 12.09c1.013 1.454 2.208 3.09 3.792 3.039c1.52-.065 2.09-.987 3.935-.987c1.831 0 2.35.987 3.96.948c1.637-.026 2.676-1.48 3.676-2.948c1.156-1.688 1.636-3.325 1.662-3.415c-.039-.013-3.182-1.221-3.22-4.857c-.026-3.04 2.48-4.494 2.597-4.559c-1.429-2.09-3.623-2.324-4.39-2.376c-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83c-1.207.052-2.662.805-3.532 1.818c-.78.896-1.454 2.338-1.273 3.714c1.338.104 2.715-.688 3.559-1.701'
      />
    </svg>
  );
}

export function GoogleMapsIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox='3.7 0 16.6 24' aria-hidden='true'>
      <path
        fill='#4285F4'
        d='M19.527 4.799c1.212 2.608.937 5.678-.405 8.173c-1.101 2.047-2.744 3.74-4.098 5.614c-.619.858-1.244 1.75-1.669 2.727c-.141.325-.263.658-.383.992c-.121.333-.224.673-.34 1.008c-.109.314-.236.684-.627.687h-.007c-.466-.001-.579-.53-.695-.887c-.284-.874-.581-1.713-1.019-2.525c-.51-.944-1.145-1.817-1.79-2.671zM8.545 7.705l-3.959 4.707c.724 1.54 1.821 2.863 2.871 4.18q.371.465.737.936l4.984-5.925l-.029.01c-1.741.601-3.691-.291-4.392-1.987a3.4 3.4 0 0 1-.209-.716c-.063-.437-.077-.761-.004-1.198zM5.492 3.149l-.003.004c-1.947 2.466-2.281 5.88-1.117 8.77l4.785-5.689l-.058-.05zM14.661.436l-3.838 4.563l.027-.01c1.6-.551 3.403.15 4.22 1.626c.176.319.323.683.377 1.045c.068.446.085.773.012 1.22l-.003.016l3.836-4.561A8.38 8.38 0 0 0 14.67.439zM9.466 5.868L14.162.285l-.047-.012A8.3 8.3 0 0 0 11.986 0a8.44 8.44 0 0 0-6.169 2.766l-.016.018z'
      />
    </svg>
  );
}

export function ChevronDownIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden
    >
      <path d='m6 9 6 6 6-6' />
    </svg>
  );
}

export function MoreHorizontalIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='currentColor'
      aria-hidden
    >
      <circle cx='5' cy='12' r='1.6' />
      <circle cx='12' cy='12' r='1.6' />
      <circle cx='19' cy='12' r='1.6' />
    </svg>
  );
}

export function SpinnerIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      aria-hidden
    >
      <circle
        cx='12'
        cy='12'
        r='9'
        stroke='currentColor'
        strokeWidth='2'
        opacity='0.25'
      />
      <path
        d='M21 12a9 9 0 0 0-9-9'
        stroke='currentColor'
        strokeWidth='2'
        strokeLinecap='round'
      />
    </svg>
  );
}

export function KeyIcon({ className }: IconProps) {
  return (
    <svg className={className} viewBox='0 0 24 24' fill='currentColor' aria-hidden>
      <path
        fillRule='evenodd'
        d='M15.75 1.5a6.75 6.75 0 0 0-6.651 7.906c.067.39-.032.794-.27 1.096L3.75 16.5v2.25A2.25 2.25 0 0 0 6 21h2.25v-2.25h2.25v-2.25h1.06l1.998-1.998c.302-.238.706-.337 1.096-.27A6.75 6.75 0 1 0 15.75 1.5Zm0 4.5a2.25 2.25 0 1 1 0 4.5 2.25 2.25 0 0 1 0-4.5Z'
        clipRule='evenodd'
      />
    </svg>
  );
}

export function EmailIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <rect x='2' y='4' width='20' height='16' rx='2' />
      <path d='m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7' />
    </svg>
  );
}

export function ApproveIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M20 6 9 17l-5-5' />
    </svg>
  );
}

export function RejectIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M18 6 6 18' />
      <path d='m6 6 12 12' />
    </svg>
  );
}

export function ShieldIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' />
    </svg>
  );
}

export function BriefcaseIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <rect x='2' y='7' width='20' height='14' rx='2' ry='2' />
      <path d='M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16' />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <line x1='12' y1='5' x2='12' y2='19' />
      <line x1='5' y1='12' x2='19' y2='12' />
    </svg>
  );
}

export function MenuIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      fill='none'
      viewBox='0 0 24 24'
      strokeWidth='1.5'
      stroke='currentColor'
    >
      <path
        strokeLinecap='round'
        strokeLinejoin='round'
        d='M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5'
      />
    </svg>
  );
}

export function CloseIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      fill='none'
      viewBox='0 0 24 24'
      strokeWidth='1.5'
      stroke='currentColor'
    >
      <path
        strokeLinecap='round'
        strokeLinejoin='round'
        d='M6 18L18 6M6 6l12 12'
      />
    </svg>
  );
}

export function StarIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 20 20'
      fill='currentColor'
      aria-hidden='true'
    >
      <path d='M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.176 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.719c-.783-.57-.38-1.81.588-1.81H7.03a1 1 0 00.95-.69l1.07-3.292z' />
    </svg>
  );
}

export function ClosedCircleIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      aria-hidden='true'
    >
      <circle cx='12' cy='12' r='9' />
      <path d='M8 8l8 8M16 8l-8 8' />
    </svg>
  );
}

export function RetryIcon({ className }: IconProps) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <path d='M3 12a9 9 0 0 1 15-6.7L21 8' />
      <path d='M21 3v5h-5' />
      <path d='M21 12a9 9 0 0 1-15 6.7L3 16' />
      <path d='M3 21v-5h5' />
    </svg>
  );
}
