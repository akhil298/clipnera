import { AuthShell } from '@/components/auth/AuthShell';
import { GoogleSignIn } from '@/components/auth/GoogleSignIn';

export default function LoginPage() {
  return (
    <AuthShell mode="login">
      <GoogleSignIn />
    </AuthShell>
  );
}
