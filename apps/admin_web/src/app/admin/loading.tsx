import { SpinnerIcon } from '@/components/icons/action-icons';

export default function AdminLoading() {
  return (
    <main className='mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-4 bg-brand-50 px-6'>
      <SpinnerIcon className='h-8 w-8 animate-spin text-ink-700' />
      <p className='text-sm text-ink-700'>Loading admin workspace...</p>
    </main>
  );
}
