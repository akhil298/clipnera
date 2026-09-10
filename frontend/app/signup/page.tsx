'use client';

import { useRouter } from 'next/navigation';
import { AuthForm } from '@/components/auth/AuthForm';

export default function SignupPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif] px-4">
      <div className="w-full max-w-md">
        <AuthForm initialMode="register" onAuthenticated={() => router.push('/dashboard')} />
      </div>
    </div>
  );
}
