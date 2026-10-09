'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock, RotateCcw } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Button, buttonClasses, Dialog, InlineAlert, useToast } from '@/components/ui';
import { saveBrandKit } from '@/lib/api/brand/kit';
import type { BrandKit } from '@/lib/api/brand/types';
import { getEntitlements } from '@/lib/api/credits';
import { isPlanError } from '@/lib/api/errors';
import { brandKeys } from '@/lib/query/keys/brand';
import { creditKeys } from '@/lib/query/keys/credits';

import { ChannelIntroSection } from '../intro';
import { PreviewPanel } from '../preview';
import { SaveBar } from './_parts/SaveBar';
import { CaptionStyleCard } from './CaptionStyleCard';
import { ExtrasCard } from './ExtrasCard';
import { IdentityCard } from './IdentityCard';
import { TypeColourCard } from './TypeColourCard';
import { useBrandKitDraft } from './useBrandKitDraft';
import { PLANS_PATH, useLeaveGuard } from './useLeaveGuard';

const UPGRADE_HREF = `${PLANS_PATH}?reason=brand_kit_edit`;
const INTRO_ANCHOR = 'channel-intro';

/** The loaded kit: form, live preview, channel intro, and the save bar. */
export function BrandKitEditor({ saved }: { saved: BrandKit }) {
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { draft, update, reset, resetKey, dirty } = useBrandKitDraft(saved);
  const [nameError, setNameError] = useState<string>();
  const guard = useLeaveGuard(dirty);

  const entitlements = useQuery({ queryKey: creditKeys.entitlements(), queryFn: ({ signal }) => getEntitlements(signal), staleTime: 60_000 });
  // Unknown plan (loading or failed) counts as allowed: the server checks again and a plan error opens plans.
  const canEdit = entitlements.data ? (entitlements.data.features.brand_kit_edit ?? entitlements.data.brand_kit_edit) : true;

  const save = useMutation({
    mutationFn: saveBrandKit,
    onSuccess: (kit) => {
      queryClient.setQueryData(brandKeys.kit(), kit);
      reset(kit);
      toast.show({ title: 'Brand kit saved', description: 'New clips use it.', tone: 'success' });
    },
    onError: (error) => {
      if (isPlanError(error)) router.push(UPGRADE_HREF);
    },
  });

  // Arriving at #channel-intro (the upload nudge, old links): the form mounts after the kit loads, so scroll then.
  useEffect(() => {
    if (window.location.hash === `#${INTRO_ANCHOR}`) document.getElementById(INTRO_ANCHOR)?.scrollIntoView();
  }, []);

  const onSave = () => {
    if (!canEdit) {
      router.push(UPGRADE_HREF);
      return;
    }
    if (!draft.brand_name.trim()) {
      setNameError('Add your brand or channel name.');
      document.getElementById('brand-name')?.focus();
      return;
    }
    setNameError(undefined);
    save.mutate(draft);
  };

  const onDiscard = () => {
    reset(saved);
    setNameError(undefined);
    save.reset();
  };

  const saveFailed = save.isError && !isPlanError(save.error);

  return (
    <>
      {!canEdit ? (
        <InlineAlert
          tone="neutral"
          title="Editing your brand kit is part of Pro"
          action={
            <Link href={UPGRADE_HREF} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
              See Pro
            </Link>
          }
        >
          Try every setting and watch the preview. Saving opens the plan options, and your edits stay here.
        </InlineAlert>
      ) : (
        !saved.is_customized && (
          <InlineAlert tone="info" title="Set your look once and every new clip uses it">
            These are the starting settings. Change anything, then save.
          </InlineAlert>
        )
      )}

      {saveFailed && (
        <InlineAlert
          tone="danger"
          live="alert"
          title="Your brand kit didn't save"
          action={
            <Button variant="secondary" size="sm" leadingIcon={<RotateCcw />} onClick={onSave}>
              Try again
            </Button>
          }
        >
          Your previous kit is still in use, and your edits are still here. {save.error.message}
        </InlineAlert>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-12">
        <PreviewPanel kit={draft} />
        <div className="min-w-0 space-y-6 lg:order-first lg:col-span-7">
          <IdentityCard kit={draft} update={update} nameError={nameError} />
          <TypeColourCard kit={draft} update={update} resetKey={resetKey} />
          <CaptionStyleCard kit={draft} update={update} entitlements={entitlements.data} />
          <ExtrasCard kit={draft} update={update} />
        </div>
      </div>

      <ChannelIntroSection brandName={saved.is_customized ? saved.brand_name : ''} />

      <SaveBar
        show={dirty}
        message="Unsaved changes"
        actions={
          <>
            <Button variant="ghost" onClick={onDiscard} disabled={save.isPending}>
              Discard
            </Button>
            <Button onClick={onSave} loading={save.isPending} loadingLabel="Saving" leadingIcon={canEdit ? undefined : <Lock />}>
              Save brand kit
            </Button>
          </>
        }
      />

      <Dialog
        open={guard.pendingHref !== null}
        onOpenChange={(open) => !open && guard.stay()}
        role="alertdialog"
        size="sm"
        title="Leave without saving?"
        description="Your changes to the brand kit will be lost. Your saved kit stays as it was."
        footer={
          <>
            <Button variant="ghost" onClick={guard.stay}>
              Keep editing
            </Button>
            <Button variant="secondary" onClick={guard.leave}>
              Leave without saving
            </Button>
          </>
        }
      />
    </>
  );
}
