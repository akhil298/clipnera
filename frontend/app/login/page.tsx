import { GoogleSignIn } from '@/components/auth/GoogleSignIn';

export default function LoginPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif] px-4">
      <div className="w-full max-w-md">
        <GoogleSignIn />
      </div>
    </div>
  );
}
