import type { Metadata } from 'next';
import { ContactLine, LegalPage } from '@/components/legal/LegalPage';

export const metadata: Metadata = { title: 'Privacy Policy · Clipnera' };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <p>
        This policy explains what Clipnera collects, why, and how you can control it. It covers the Clipnera web app
        and the connected publishing features that post clips to YouTube, TikTok, Instagram and X on your behalf.
      </p>

      <h2>Information you give us</h2>
      <ul>
        <li>Account details: your email address, name and password (stored only as a salted hash), or the basic profile from Google or Microsoft if you sign in with them.</li>
        <li>Videos you upload or link, and the clips, transcripts and captions Clipnera generates from them.</li>
        <li>Payment records for manual UPI payments: the transaction reference and the proof you upload.</li>
      </ul>

      <h2>Connected publishing platforms</h2>
      <p>
        Connecting a social account is optional. We request only the permissions needed to show which account you
        connected and to publish the clips you choose. We do not read your messages, comments, analytics or other
        posts.
      </p>
      <ul>
        <li>
          <b>YouTube</b> (YouTube API Services): <code>youtube.upload</code> to upload the videos you publish, and{' '}
          <code>youtube.readonly</code> to read your channel&apos;s ID, name, handle, picture and subscriber count.
        </li>
        <li>
          <b>TikTok</b>: <code>user.info.basic</code>, <code>user.info.profile</code> and <code>user.info.stats</code>{' '}
          for your account ID, display name, username, picture and follower count; <code>video.publish</code> to post
          the videos you publish. Before each post we read your current posting options (such as who can view it).
        </li>
        <li>
          <b>Instagram</b>: <code>instagram_business_basic</code> for your professional account&apos;s ID, username,
          picture and follower count; <code>instagram_business_content_publish</code> to publish reels.
        </li>
        <li>
          <b>X</b>: <code>users.read</code> and <code>tweet.read</code> for your account ID, handle, picture and
          follower count; <code>tweet.write</code> and <code>media.write</code> to post the videos you publish;{' '}
          <code>offline.access</code> so scheduled posts can go out while you are away.
        </li>
      </ul>
      <p>
        We store the access credentials each platform issues, encrypted with AES-256-GCM using keys kept outside our
        database. They are never shown to you, to our staff or in our admin tools, and are used only to publish the
        posts you create and to refresh your profile details about once a day. For each post we keep the clip,
        caption, platform settings, scheduled time, and the resulting post ID and link.
      </p>
      <p>
        Videos are sent to the platform you choose. For Instagram, the platform downloads the video through a private
        link that expires within 15 minutes.
      </p>

      <h2>How we use information</h2>
      <ul>
        <li>To provide Clipnera: processing videos, generating clips and publishing them where you ask.</li>
        <li>To run your plan: usage limits, credits and billing.</li>
        <li>To keep the service secure and to send emails about your account, such as a failed post or an account that needs reconnecting.</li>
      </ul>
      <p>We do not sell your information or use data from connected platforms for advertising.</p>

      <h2>Service providers</h2>
      <p>
        We store data with Amazon Web Services and use AI providers (such as Anthropic and Groq) to transcribe and
        analyse your videos. They process data only to provide those services to us.
      </p>

      <h2>Retention and deletion</h2>
      <ul>
        <li>
          <b>Disconnecting an account</b> (Settings → Social accounts) cancels its scheduled posts, revokes Clipnera&apos;s
          access where the platform allows it, and deletes the stored credentials and profile details.
        </li>
        <li>
          <b>Removing Clipnera from the platform</b> (for example in Instagram or TikTok settings) has the same effect.
          If you ask Meta to delete your data, we delete the account&apos;s credentials, posts and identifiers and give you
          a confirmation code you can check on our <a href="/data-deletion">data deletion status page</a>.
        </li>
        <li>You can revoke Google access at any time at <a href="https://myaccount.google.com/permissions">Google security settings</a>.</li>
        <li>To delete your Clipnera account and everything in it, contact us at <ContactLine />.</li>
      </ul>

      <h2>Third-party terms</h2>
      <p>
        Publishing to YouTube uses YouTube API Services. By connecting YouTube you agree to the{' '}
        <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>, and Google&apos;s handling of your data is
        described in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>. TikTok, Instagram and X
        handle data under their own terms and privacy policies.
      </p>

      <h2>Contact</h2>
      <p>
        Questions or requests about your data: <ContactLine />.
      </p>
    </LegalPage>
  );
}
