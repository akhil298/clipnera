import type { Metadata } from 'next';
import { BUSINESS, BusinessDetails, LegalPage } from '@/components/legal/LegalPage';

export const metadata: Metadata = { title: 'Terms of Service · Clipnera' };

export default function TermsPage() {
  const operator = BUSINESS.legalName || 'the operator of Clipnera';
  return (
    <LegalPage title="Terms of Service">
      <p>
        These terms are an agreement between you and {operator} (&quot;we&quot;). By creating an account or using Clipnera
        you agree to them, to our <a href="/privacy">Privacy Policy</a> and to our <a href="/refunds">Refund Policy</a>.
      </p>

      <h2>Who can use Clipnera</h2>
      <p>
        You must be 18 or older and able to enter a binding contract. If you use Clipnera for a business, you confirm you
        can accept these terms for it.
      </p>

      <h2>Your content</h2>
      <p>
        You keep ownership of the videos you upload and the clips made from them. You confirm you have the rights to
        upload them and to publish them wherever you direct Clipnera to. You give us the permission needed to store,
        process and publish them for you.
      </p>
      <p>
        When you paste a link to a video, you confirm you own that video or have permission to download and edit it. Do
        not submit other people&apos;s videos without their permission.
      </p>

      <h2>AI output</h2>
      <p>
        Clips, captions, scores, titles and other output are generated automatically and can be inaccurate. Scores such as
        virality are estimates, not predictions of views or reach. Review everything before you publish it.
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

      <h2>Plans, credits and payments</h2>
      <ul>
        <li>
          Prices are set in US dollars ($). Payment is by UPI in Indian rupees (₹), converted at that day&apos;s exchange rate;
          the rupee amount is shown at checkout before you pay, and the amount you pay is the amount shown. There are no
          setup, processing or hidden fees.
        </li>
        <li>
          Pro is paid monthly or yearly by UPI. It does not renew automatically: when the period ends your account returns
          to the Free plan unless you pay again.
        </li>
        <li>
          Plan credits reset every 30 days and do not roll over. Credits bought in packs never expire and are used after
          your plan&apos;s credits.
        </li>
        <li>Payments are verified manually before a plan or credits are activated.</li>
        <li>
          Refunds are covered by our <a href="/refunds">Refund Policy</a>.
        </li>
      </ul>

      <h2>Acceptable use</h2>
      <p>
        Do not use Clipnera to post content you do not have rights to, spam, or anything that breaks the law or a
        platform&apos;s rules. Do not try to get around plan limits, share accounts, or disrupt the service. We may suspend
        accounts or connected publishing that does.
      </p>

      <h2>Ending your account</h2>
      <p>
        You can delete your account at any time in Settings → Profile. This deletes your data as described in the{' '}
        <a href="/privacy">Privacy Policy</a> and cannot be undone. We may suspend or close accounts that break these terms,
        and will tell you why unless the law prevents us.
      </p>

      <h2>Disclaimer and liability</h2>
      <p>
        Clipnera is provided as is. To the extent the law allows, we are not liable for indirect losses, lost profits or
        lost views, or for how third-party platforms handle your posts, and our total liability is limited to the amount
        you paid us in the 12 months before the claim. Nothing in these terms limits rights you have under consumer
        protection law.
      </p>

      <h2>Changes</h2>
      <p>
        We may update these terms. If a change matters, we will tell you by email or in the app before it takes effect.
        Continuing to use Clipnera after that means you accept the new terms.
      </p>

      <h2>Governing law</h2>
      <p>These terms are governed by the laws of India.</p>

      <h2>Contact</h2>
      <BusinessDetails />
    </LegalPage>
  );
}
