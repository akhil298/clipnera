import { permanentRedirect } from 'next/navigation';

/** Legacy tab id: `?tab=social` (the OAuth return) arrives here through middleware's 308. */
export default function SocialAlias() {
  permanentRedirect('/dashboard/settings/connections');
}
