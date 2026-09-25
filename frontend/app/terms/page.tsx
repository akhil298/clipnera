import type { Metadata } from 'next';
import { ContactLine, LegalPage } from '@/components/legal/LegalPage';

export const metadata: Metadata = { title: 'Terms of Service · Clipnera' };

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service">
      <p>By using Clipnera you agree to these terms.</p>

      <h2>Your content</h2>
      <p>
        You keep ownership of the videos you upload and the clips made from them. You confirm you have the rights to
        upload them and to publish them wherever you direct Clipnera to. You give us the permission needed to store,
        process and publish them for you.
      </p>

      <h2>Connected platforms</h2>
      <ul>
        <li>Clipnera publishes only what you choose, to the accounts you connect, at the time you set.</li>
        <li>
          Each platform&apos;s own rules apply to what you post, including the{' '}
          <a href="https://www.youtube.com/t/terms">YouTube Terms of Service</a>, TikTok&apos;s Terms of Service and
          Music Usage Confirmation, Instagram&apos;s Terms of Use and X&apos;s Terms of Service.
        </li>
        <li>
          Platforms can limit, delay or reject posts, and may restrict posts to private while Clipnera&apos;s app is under
          their review. We show these limits in the app but cannot guarantee a post goes out.
        </li>
        <li>You can disconnect an account at any time in Settings.</li>
      </ul>

      <h2>Plans and payments</h2>
      <p>
        Paid features and limits are described on the plan page. Payments are verified manually before a plan is
        activated.
      </p>

      <h2>Acceptable use</h2>
      <p>
        Do not use Clipnera to post content you do not have rights to, spam, or anything that breaks the law or a
        platform&apos;s rules. We may suspend accounts or connected publishing that does.
      </p>

      <h2>Disclaimer</h2>
      <p>
        Clipnera is provided as is. To the extent the law allows, we are not liable for indirect losses, or for how
        third-party platforms handle your posts.
      </p>

      <h2>Contact</h2>
      <p>
        <ContactLine />
      </p>
    </LegalPage>
  );
}
