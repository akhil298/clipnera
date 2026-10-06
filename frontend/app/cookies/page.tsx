import type { Metadata } from 'next';
import { BusinessDetails, COOKIE_NOTICE_KEY, LegalPage } from '@/components/legal/LegalPage';

export const metadata: Metadata = { title: 'Cookie Policy · Clipnera' };

const STORAGE = [
  { name: 'token, token_expires_at', where: 'Local storage', purpose: 'Keeps you signed in.', kept: 'Until you sign out or the session expires' },
  { name: 'google_oauth_state, google_accept_terms', where: 'Session storage', purpose: 'Protects Google sign-in from forged requests and carries your sign-up confirmation to the next page.', kept: 'Until the sign-in finishes or the tab closes' },
  { name: COOKIE_NOTICE_KEY, where: 'Local storage', purpose: 'Remembers that you closed this notice.', kept: 'Until you clear site data' },
  { name: 'clipnera_referral_code', where: 'Local storage', purpose: 'Holds the code from a referral link you opened, to fill in the welcome form.', kept: 'Until you finish the welcome form' },
  { name: 'clipnera_referral_card_dismissed', where: 'Local storage', purpose: 'Remembers that you closed the referral card on Home.', kept: 'Until you clear site data' },
];

export default function CookiePolicyPage() {
  return (
    <LegalPage title="Cookie Policy">
      <p>
        Clipnera does not use advertising, analytics or tracking cookies, and does not load third-party scripts that do.
        We only store what the app needs to work, so there is nothing to opt in to or out of.
      </p>

      <h2>What your browser stores</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border border-neutral-800 [&_th]:text-left [&_th]:p-2 [&_th]:text-white [&_th]:bg-neutral-900 [&_td]:p-2 [&_td]:align-top [&_tr]:border-t [&_tr]:border-neutral-800">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Type</th>
              <th scope="col">Purpose</th>
              <th scope="col">Kept</th>
            </tr>
          </thead>
          <tbody>
            {STORAGE.map((item) => (
              <tr key={item.name}>
                <td>
                  <code>{item.name}</code>
                </td>
                <td>{item.where}</td>
                <td>{item.purpose}</td>
                <td>{item.kept}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>All of these are strictly necessary and are never shared with anyone.</p>

      <h2>Third parties</h2>
      <p>
        When you choose <b>Continue with Google</b> you go to Google&apos;s sign-in page, where Google may set its own
        cookies under the <a href="https://policies.google.com/technologies/cookies">Google cookie policy</a>. The same applies
        on YouTube, TikTok, Instagram or X when you connect one of those accounts. Fonts and all other files are served by
        Clipnera itself.
      </p>

      <h2>Controlling storage</h2>
      <p>
        You can clear this data at any time in your browser settings. Clearing it signs you out.
      </p>

      <h2>Contact</h2>
      <BusinessDetails />
    </LegalPage>
  );
}
