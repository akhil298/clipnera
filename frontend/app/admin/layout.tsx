import { AdminGate } from '@/components/admin/AdminGate';

export default function AdminRootLayout({ children }: { children: React.ReactNode }) {
  return <AdminGate>{children}</AdminGate>;
}
