import type { Metadata } from 'next';
import { BusinessDetails, ContactLine, LegalPage } from '@/components/legal/LegalPage';

export const metadata: Metadata = { title: 'Refund Policy · Clipnera' };

export default function RefundPolicyPage() {
  return (
    <LegalPage title="Refund Policy">
      <p>
        Payments for the Pro plan and for credit packs are final and are not refunded, except in the cases below. Please
        try Clipnera on the Free plan before you pay.
      </p>

      <h2>Failed processing: credits back automatically</h2>
      <p>
        If Clipnera fails to process a video, the credits it used are returned to your balance automatically. You do not
        need to ask.
      </p>

      <h2>When we refund your money</h2>
      <ul>
        <li>You paid twice for the same purchase.</li>
        <li>You paid a different amount from the one shown, or paid for something we could not activate.</li>
        <li>We rejected your payment after the money reached us.</li>
        <li>We stop providing the service you paid for before your paid period ends; we refund the unused part.</li>
      </ul>
      <p>
        We do not refund unused plan credits, the rest of a monthly or yearly period after you stop using Clipnera, or
        purchases on accounts suspended for breaking our <a href="/terms">Terms of Service</a>.
      </p>

      <h2>No automatic renewal</h2>
      <p>
        Pro does not renew or charge you automatically. When your period ends your account returns to the Free plan unless
        you choose to pay again, so there is nothing to cancel.
      </p>

      <h2>How to ask for a refund</h2>
      <p>
        Email <ContactLine /> from your account email with the UPI transaction reference (UTR) and what went wrong. We
        reply within 7 working days. Approved refunds go back to the UPI account you paid from.
      </p>

      <p>This policy does not affect your rights under the Consumer Protection Act, 2019.</p>

      <h2>Contact</h2>
      <BusinessDetails />
    </LegalPage>
  );
}
