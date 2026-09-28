import { AuthShell } from '@/components/auth/AuthShell';
import { GoogleSignIn } from '@/components/auth/GoogleSignIn';

export default function SignupPage() {
  return (
    <AuthShell mode="register">
      <GoogleSignIn mode="register" />
    </AuthShell>
  );
}
