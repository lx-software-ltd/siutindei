import { LoginLoadingNotice } from '@/components/login/login-loading-notice';

export default function AdminLoading() {
  return (
    <main className='mx-auto flex min-h-screen max-w-lg items-center bg-brand-50 px-6'>
      <LoginLoadingNotice />
    </main>
  );
}
