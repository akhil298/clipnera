import { permanentRedirect } from 'next/navigation';

/** Legacy tab id: `?tab=team` arrives here through middleware's 308. */
export default function TeamAlias() {
  permanentRedirect('/dashboard/settings/workspace');
}
