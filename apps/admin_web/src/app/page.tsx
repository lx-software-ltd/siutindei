'use client';

import { AdminDashboard } from '../components/admin/admin-dashboard';
import { AuthGate } from '../components/auth-gate';
import { AuthProvider } from '../components/auth-provider';
import { LoginScreen } from '../components/login-screen';

export default function HomePage() {
  return (
    <AuthProvider>
      <AuthGate requireAuth={false} signedIn={<AdminDashboard />}>
        <LoginScreen />
      </AuthGate>
    </AuthProvider>
  );
}
