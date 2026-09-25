'use client';

import { useEffect, useState } from 'react';
import { getDataDeletionStatus, type DataDeletionStatusResponse } from '@/lib/api';
import { LegalPage } from '@/components/legal/LegalPage';
import { formatDate } from '@/lib/utils/dates';

/** Where Meta sends people to check a data deletion request (?code=…). */
export default function DataDeletionPage() {
  const [status, setStatus] = useState<DataDeletionStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get('code');
    if (!code) {
      setError('No confirmation code given.');
      return;
    }
    getDataDeletionStatus(code).then(setStatus).catch((err: Error) => setError(err.message));
  }, []);

  return (
    <LegalPage title="Data deletion request">
      <p>
        When you remove Clipnera from a connected platform and ask for your data to be deleted, we delete that
        account&apos;s stored credentials, profile details and posts. See the <a href="/privacy">privacy policy</a>.
      </p>
      {error && <p className="text-rose-300">{error}</p>}
      {status && (
        <div className="p-4 rounded-xl bg-neutral-900 border border-neutral-800 space-y-1">
          <p>
            Confirmation code: <code>{status.confirmation_code}</code>
          </p>
          <p>Requested: {formatDate(status.requested_at)}</p>
          <p>Status: {status.completed ? 'Completed — the data has been deleted.' : 'In progress.'}</p>
        </div>
      )}
    </LegalPage>
  );
}
