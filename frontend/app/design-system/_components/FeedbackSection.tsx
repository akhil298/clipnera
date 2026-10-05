'use client';

import { useState } from 'react';

import { Accordion, Avatar, Banner, Button, Disclosure, InlineAlert, Spinner, UploadProgressItem } from '@/components/ui';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

export function FeedbackSection() {
  const [banner, setBanner] = useState(true);

  return (
    <GallerySection id="feedback" title="Messages and disclosure" intro="Banners for app-wide notices, inline alerts for this place only, show-more sections, upload rows and avatars.">
      <Specimen title="Banner" note="A strip under the top bar; one at a time, most severe wins. Tone is in an icon and a spoken word as well as colour.">
        <div className="space-y-3 overflow-hidden rounded-cn-lg border border-cn-border">
          {banner && (
            <Banner tone="warning" title="Your YouTube connection ends in 2 days." action={<Button size="sm" variant="secondary">Reconnect</Button>} onDismiss={() => setBanner(false)}>
              Scheduled posts pause until you reconnect.
            </Banner>
          )}
          <Banner tone="danger" title="Payment failed." action={<Button size="sm">Update card</Button>}>
            Your plan stays active until 12 October.
          </Banner>
          <Banner tone="info">You are offline. Changes are kept and sync when you are back.</Banner>
        </div>
      </Specimen>

      <Specimen title="InlineAlert" note="Stays in place inside content. live='alert' only for an error that just happened.">
        <div className="grid gap-3 md:grid-cols-2">
          <InlineAlert tone="info" title="Captions use English">Change the language in Options before you start.</InlineAlert>
          <InlineAlert tone="success" title="Brand kit saved" />
          <InlineAlert tone="warning" title="You have 40 credits left" action={<Button size="sm" variant="secondary">Add credits</Button>}>
            This export needs about 60.
          </InlineAlert>
          <InlineAlert tone="danger" live="alert" title="The link could not be read." action={<Button size="sm">Try again</Button>} onDismiss={() => undefined}>
            Nothing was uploaded. Check the link is public.
          </InlineAlert>
        </div>
      </Specimen>

      <Specimen title="Disclosure and Accordion" note="A button inside a heading with aria-expanded; height collapses in 200 ms, instantly under reduced motion.">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <Disclosure title="Options" summary="Auto · 9:16 · English">
              Language, clip length, layout and captions.
            </Disclosure>
            <Disclosure title="Details" variant="card" defaultOpen>
              Steps and the timeline operations, in plain words.
            </Disclosure>
            <Disclosure title="Advanced" disabled>
              Hidden.
            </Disclosure>
          </div>
          <Accordion
            type="single"
            defaultValue={['credits']}
            items={[
              { id: 'credits', title: 'How are credits counted?', content: 'One credit per minute of source video, rounded up.' },
              { id: 'expire', title: 'Do pack credits expire?', content: 'No. Plan credits renew monthly; pack credits never expire.' },
              { id: 'refund', title: 'What happens if a run fails?', content: 'Credits held for it are returned.' },
            ]}
          />
        </div>
      </Specimen>

      <Specimen title="UploadProgressItem" note="Each state shows only the actions that apply.">
        <div className="divide-y divide-cn-border rounded-cn-lg border border-cn-border bg-cn-surface px-3">
          <UploadProgressItem name="episode-12-founders.mp4" meta="1.2 GB" status="uploading" percent={42} eta="3 min left" onPause={() => undefined} onCancel={() => undefined} />
          <UploadProgressItem name="keynote-2025.mov" meta="3.8 GB" status="paused" percent={18} onResume={() => undefined} onCancel={() => undefined} />
          <UploadProgressItem name="interview-raw.mp4" status="processing" step="Finding moments" onCancel={() => undefined} />
          <UploadProgressItem name="teaser.mp4" status="queued" meta="210 MB" onCancel={() => undefined} />
          <UploadProgressItem name="broll-city.mp4" status="done" meta="88 MB · 0:42" action={<Button size="sm" variant="ghost">Open</Button>} onDismiss={() => undefined} />
          <UploadProgressItem name="podcast-ep9.mp4" status="failed" error="Connection dropped. Uploaded parts are kept." onRetry={() => undefined} onDismiss={() => undefined} />
        </div>
      </Specimen>

      <Specimen title="Avatar and Spinner" note="Avatars fall back to initials; workspaces are rounded squares. Spinner only where no step can be named.">
        <StateGrid>
          <State label="sizes">
            <span className="flex items-center gap-2">
              <Avatar name="Asha Rao" size={24} />
              <Avatar name="Asha Rao" size={32} />
              <Avatar name="Asha Rao" size={40} labelled status="online" />
            </span>
          </State>
          <State label="workspace">
            <Avatar name="Rao Studio" shape="workspace" size={40} labelled />
          </State>
          <State label="broken image">
            <Avatar name="Vikram Shah" src="/missing.png" size={40} labelled />
          </State>
          <State label="spinner">
            <Spinner label="Connecting to YouTube" showLabel />
          </State>
        </StateGrid>
      </Specimen>
    </GallerySection>
  );
}
