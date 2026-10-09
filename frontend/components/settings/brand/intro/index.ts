import { createElement } from 'react';

import { SettingsCard } from '../form/_parts/SettingsCard';

/**
 * Placeholder for the channel intro (screens/03 §16.3). Unit U8 replaces this
 * folder with the real editor, the "Play before every export" switch and
 * `ChannelIntroNudge`. The anchor id `channel-intro` is the entry point that
 * links and the upload nudge use, so it must stay.
 */
export function ChannelIntroSection(_props: { brandName: string }) {
  return createElement(SettingsCard, {
    id: 'channel-intro',
    className: 'scroll-mt-16',
    title: 'Channel intro',
    description:
      "A 6-second intro with your name, what your channel is about, and a cursor tapping your platform's Like and Subscribe or Follow. Made once, then played before every clip you export.",
  });
}
