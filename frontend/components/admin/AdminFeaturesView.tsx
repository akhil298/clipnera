'use client';

import React, { useState } from 'react';
import { AdminLayout } from './AdminLayout';
import { FeatureSwitches } from './FeatureSwitches';

/** Every feature switch except social publishing, which has its own page. */
export function AdminFeaturesView() {
  const [error, setError] = useState<string | null>(null);
  return (
    <AdminLayout
      title="Features"
      subtitle="Turn features on or off for every user. New features ship off; the API refuses what is off and the app hides it."
    >
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}
      <section className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-3">
        <FeatureSwitches show={(key) => !key.startsWith('social_publishing')} onError={setError} />
      </section>
    </AdminLayout>
  );
}
