import { LoginBackdrop } from '@/components/login/login-backdrop';
import { LoginBrandHeader } from '@/components/login/login-brand-header';
import { StatusBanner } from '@/components/status-banner';

export default function AdminLoading() {
  return (
    <LoginBackdrop>
      <LoginBrandHeader />
      <StatusBanner kind='info'>Loading admin workspace...</StatusBanner>
    </LoginBackdrop>
  );
}
