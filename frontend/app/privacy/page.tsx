import type { Metadata } from 'next';
import { BusinessDetails, ContactLine, LegalPage } from '@/components/legal/LegalPage';

export const metadata: Metadata = { title: 'Privacy Policy · Clipnera' };

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy">
      <p>
        This policy explains what Clipnera collects, why, and how you can control it. It covers the Clipnera web app
        and the connected publishing features that post clips to YouTube, TikTok, Instagram and X on your behalf. We
        act as the data fiduciary (data controller) for this information.
      </p>

      <h2>Information you give us</h2>
      <ul>
        <li>
          Account details: the email address, name and profile picture Google shares when you sign in with Google. For
          accounts created before Google sign-in, a password stored only as a salted hash.
        </li>
        <li>When you confirmed you are 18 or older and accepted our Terms and this policy.</li>
        <li>Videos you upload or link, and the clips, transcripts, captions, brand kits and reels Clipnera generates from them.</li>
        <li>Payment records for manual UPI payments: the plan or credit pack, amount, UPI transaction reference (UTR) and the payment screenshot you upload.</li>
        <li>Feedback you give on a clip (for example, a thumbs up or down).</li>
        <li>Your answers to the welcome form: what you do and how you heard about Clipnera.</li>
        <li>
          Referrals: the referral code you joined with, if any. The person who referred you sees your first name, last
          initial and a partly hidden email address, and whether you reached each step in time; never your videos or
          payments.
        </li>
      </ul>

      <h2>Information we collect automatically</h2>
      <ul>
        <li>
          Sign-in history: when you signed in, how, and the IP address and browser used. The IP address and browser are
          erased after 90 days.
        </li>
        <li>The days on which you used Clipnera, and your credit and feature usage, to enforce plan limits.</li>
        <li>
          We do not use analytics, advertising or tracking tools, and we do not collect your phone number, location or
          contacts. See the <a href="/cookies">cookie policy</a> for what your browser stores.
        </li>
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
        <li>
          To keep the service secure and to send emails about your account, such as a failed post or an account that
          needs reconnecting. Every such email has an unsubscribe link, and you can turn them off in Settings.
        </li>
      </ul>
      <p>
        We process this information to provide the service you signed up for and on the basis of the consent you give
        when you create an account. We do not sell your information, send marketing emails, or use data from connected
        platforms for advertising.
      </p>

      <h2>Service providers</h2>
      <p>These providers process data only to provide their service to us:</p>
      <ul>
        <li>Amazon Web Services: hosting, file storage and account emails.</li>
        <li>Google: sign-in, and the Gemini API for AI analysis and generated B-roll.</li>
        <li>Groq, OpenAI, Anthropic and xAI: transcription, clip analysis, captions and voiceovers.</li>
        <li>Pexels and Pixabay: stock footage searches. They receive search words only, never your videos or account details.</li>
      </ul>
      <p>
        Some of these providers are outside India, so your data may be processed in other countries, including the
        United States.
      </p>

      <h2>Children</h2>
      <p>
        Clipnera is only for people aged 18 or older, and you must confirm your age to create an account. We do not
        knowingly collect data from anyone under 18. If you believe a child has an account, contact us and we will delete
        it.
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
        <li>
          <b>Deleting your account</b> (Settings → Profile → Delete account) immediately and permanently deletes your
          account, videos, clips, reels, brand kits, payment records and connected accounts. You can also ask us to do
          it at <ContactLine />.
        </li>
        <li>
          When an account joins through a referral, we keep a one-way hash of its email address after the account is
          deleted, only to stop the same address earning a referral reward twice. The hash cannot be turned back into the
          address.
        </li>
        <li>Otherwise we keep your data for as long as your account exists.</li>
      </ul>

      <h2>Your rights</h2>
      <p>
        You can ask to access, correct or delete your personal data, withdraw your consent, and nominate someone to
        exercise these rights for you if you die or become unable to. Withdrawing consent means deleting your account,
        because we cannot provide the service without it. Contact us at <ContactLine /> and we will respond within 30
        days. If you are not satisfied with our response, you can complain to the Data Protection Board of India.
      </p>

      <h2>Third-party terms</h2>
      <p>
        Publishing to YouTube uses YouTube API Services. By connecting YouTube you agree to the{' '}
        <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>, and Google&apos;s handling of your data is
        described in the <a href="https://policies.google.com/privacy">Google Privacy Policy</a>. TikTok, Instagram and X
        handle data under their own terms and privacy policies.
      </p>

      <h2>Changes</h2>
      <p>
        If we change this policy in a way that matters, we will tell you by email or in the app before the change takes
        effect.
      </p>

      <h2>Contact</h2>
      <p>Questions, requests or complaints about your data:</p>
      <BusinessDetails />
    </LegalPage>
  );
}
