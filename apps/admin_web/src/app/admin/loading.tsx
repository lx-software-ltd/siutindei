import { SpinnerIcon } from '@/components/icons/action-icons';

export default function AdminLoading() {
  return (
    <main className='mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-4 px-6'>
      <SpinnerIcon className='h-8 w-8 animate-spin text-slate-700' />
      <p className='text-sm text-slate-600'>Loading admin workspace...</p>
    </main>
  );
}
