'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { CalendarDays, Loader2, Send } from 'lucide-react';
import {
  socialApi,
  type ConnectedAccountResponse,
  type SocialConnectionsResponse,
  type SocialPlatform,
  type TikTokCreatorInfoResponse,
} from '@/lib/api';
import type { ViralClip } from '@/lib/types';
import { utcToZonedLocal, zonedLocalToUtc } from '@/lib/utils/timezones';
import { ProLockBadge } from '@/components/dashboard/ProLockBadge';
import { usePlan } from '@/hooks/usePlan';
import { PLATFORM_STYLE, SOCIAL_SETTINGS_PATH } from './platforms';
import { Select, SelectOption } from '@/components/ui/Select';

type Options = Record<string, unknown>;

const TIKTOK_PRIVACY_LABELS: Record<string, string> = {
  PUBLIC_TO_EVERYONE: 'Everyone',
  MUTUAL_FOLLOW_FRIENDS: 'Friends',
  FOLLOWER_OF_CREATOR: 'Followers',
  SELF_ONLY: 'Only me',
};

const YOUTUBE_PRIVACY_OPTIONS: SelectOption<string>[] = [
  { value: 'public', label: 'Public' },
  { value: 'unlisted', label: 'Unlisted' },
  { value: 'private', label: 'Private' },
];

function defaultOptions(platform: SocialPlatform, clip: ViralClip | undefined): Options {
  switch (platform) {
    case 'youtube':
      // made_for_kids is deliberately unset: YouTube requires the creator to answer it.
      return { title: (clip?.title ?? '').slice(0, 100), privacy_status: 'public' };
    case 'tiktok':
      // No preselected privacy level: TikTok requires the creator to choose.
      return {
        disable_comment: false,
        disable_duet: false,
        disable_stitch: false,
        brand_content_toggle: false,
        brand_organic_toggle: false,
      };
    case 'instagram':
      return { share_to_feed: true };
    default:
      return {};
  }
}

function newSubmitKey(): string {
  return crypto.randomUUID().replace(/-/g, '');
}

interface PublishComposerProps {
  clip: ViralClip | undefined;
  /** The caption from the composer above; each platform starts from it. */
  baseCaption: string;
  timeZone: string;
  onPublished: () => void;
}

export function PublishComposer({ clip, baseCaption, timeZone, onPublished }: PublishComposerProps) {
  const { promptUpgrade } = usePlan();
  const [connections, setConnections] = useState<SocialConnectionsResponse | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [captions, setCaptions] = useState<Record<string, string>>({});
  const [options, setOptions] = useState<Record<string, Options>>({});
  const [creatorInfo, setCreatorInfo] = useState<Record<string, TikTokCreatorInfoResponse | 'error'>>({});
  const [mode, setMode] = useState<'now' | 'schedule'>('now');
  const [when, setWhen] = useState(() => utcToZonedLocal(new Date(Date.now() + 60 * 60 * 1000), timeZone));
  const [submitKey, setSubmitKey] = useState(newSubmitKey);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    socialApi.getConnections().then(setConnections).catch((err) => setError(err.message));
  }, []);

  const usable = useMemo(
    () =>
      (connections?.accounts ?? []).filter((account) => {
        const info = connections?.platforms.find((p) => p.platform === account.platform);
        return account.status === 'active' && info?.available && info.allowed_by_plan;
      }),
    [connections],
  );
  const chosen = usable.filter((account) => selected.includes(account.id));

  // A fresh form (new key) whenever what is being posted changes.
  useEffect(() => setSubmitKey(newSubmitKey()), [clip?.id, selected, mode, when]);

  const toggle = (account: ConnectedAccountResponse) => {
    const isOn = selected.includes(account.id);
    setSelected(isOn ? selected.filter((id) => id !== account.id) : [...selected, account.id]);
    if (!isOn) {
      setOptions((prev) => ({ ...prev, [account.id]: prev[account.id] ?? defaultOptions(account.platform, clip) }));
      if (account.platform === 'tiktok' && !creatorInfo[account.id]) {
        socialApi
          .getTikTokCreatorInfo(account.id)
          .then((info) => setCreatorInfo((prev) => ({ ...prev, [account.id]: info })))
          .catch(() => setCreatorInfo((prev) => ({ ...prev, [account.id]: 'error' })));
      }
    }
  };

  const setOption = (accountId: string, key: string, value: unknown) =>
    setOptions((prev) => ({ ...prev, [accountId]: { ...prev[accountId], [key]: value } }));

  const captionFor = (accountId: string) => captions[accountId] ?? baseCaption;

  const submit = async () => {
    if (!clip || chosen.length === 0) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const scheduledAt = mode === 'schedule' ? zonedLocalToUtc(when, timeZone).toISOString() : null;
      const res = await socialApi.createPosts({
        clip_id: clip.id,
        targets: chosen.map((account) => ({
          account_id: account.id,
          caption: captionFor(account.id),
          options: options[account.id] ?? {},
        })),
        scheduled_at: scheduledAt,
        idempotency_key: submitKey,
      });
      setNotice(
        mode === 'now'
          ? `Publishing to ${res.posts.length} account${res.posts.length === 1 ? '' : 's'}…`
          : `Scheduled ${res.posts.length} post${res.posts.length === 1 ? '' : 's'}.`,
      );
      setSelected([]);
      setCaptions({});
      onPublished();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not publish');
    } finally {
      setSubmitting(false);
    }
  };

  if (!connections) {
    return (
      <div className="flex items-center gap-2 text-xs text-neutral-400 pt-2 border-t border-neutral-800">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading connected accounts…
      </div>
    );
  }

  return (
    <div className="space-y-3 pt-2 border-t border-neutral-800">
      <label className="text-xs font-bold text-neutral-300 block">Publish to:</label>
      {usable.length === 0 ? (
        <p className="text-[11px] text-neutral-400">
          No connected accounts yet.{' '}
          <Link href={SOCIAL_SETTINGS_PATH} className="text-amber-300 hover:underline">
            Connect one in Settings
          </Link>
          .
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {usable.map((account) => {
            const isOn = selected.includes(account.id);
            return (
              <button
                key={account.id}
                onClick={() => toggle(account)}
                className={`px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border transition-all flex items-center gap-1.5 ${
                  isOn
                    ? 'bg-neutral-900 border-amber-500/60 text-white ring-1 ring-amber-500/30'
                    : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:border-neutral-700'
                }`}
              >
                <span className={`w-2 h-2 rounded-full bg-gradient-to-r ${PLATFORM_STYLE[account.platform].color}`} />
                {PLATFORM_STYLE[account.platform].name} · {account.handle || account.display_name}
              </button>
            );
          })}
        </div>
      )}

      {chosen.map((account) => {
        const info = connections.platforms.find((p) => p.platform === account.platform);
        const caption = captionFor(account.id);
        const opts = options[account.id] ?? {};
        return (
          <div key={account.id} className="p-3 rounded-lg bg-neutral-950 border border-neutral-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-white">
                {PLATFORM_STYLE[account.platform].name} · {account.handle || account.display_name}
              </span>
              <span className={`text-[10px] font-mono ${caption.length > (info?.caption_max_chars ?? 0) ? 'text-rose-400' : 'text-neutral-500'}`}>
                {caption.length}/{info?.caption_max_chars}
              </span>
            </div>
            <textarea
              rows={2}
              value={caption}
              onChange={(e) => setCaptions((prev) => ({ ...prev, [account.id]: e.target.value }))}
              className="w-full p-2 rounded-lg bg-neutral-900 border border-neutral-800 text-xs text-neutral-200 focus:outline-none focus:border-amber-400 resize-none"
            />
            <PlatformOptions
              platform={account.platform}
              options={opts}
              creator={creatorInfo[account.id]}
              onChange={(key, value) => setOption(account.id, key, value)}
            />
            {info?.pending_review_note && (
              <p className="text-[10px] text-amber-300/80">{info.pending_review_note}</p>
            )}
          </div>
        );
      })}

      <div className="flex flex-wrap items-center gap-2">
        {(['now', 'schedule'] as const).map((value) => {
          const locked = value === 'schedule' && !connections.can_schedule;
          return (
            <button
              key={value}
              onClick={() =>
                locked ? promptUpgrade('Scheduling social posts is a Pro feature.') : setMode(value)
              }
              className={`px-3 py-1.5 rounded-lg text-[11px] font-bold border flex items-center gap-1.5 ${
                mode === value ? 'bg-neutral-800 border-neutral-600 text-white' : 'bg-neutral-950 border-neutral-800 text-neutral-400'
              }`}
            >
              {value === 'now' ? 'Publish now' : 'Schedule'}
              {locked && <ProLockBadge />}
            </button>
          );
        })}
        {mode === 'schedule' && (
          <input
            type="datetime-local"
            value={when}
            onChange={(e) => setWhen(e.target.value)}
            className="px-2 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-[11px] text-white focus:outline-none focus:border-amber-400"
          />
        )}
      </div>

      {error && <p className="text-[11px] text-rose-300">{error}</p>}
      {notice && <p className="text-[11px] text-emerald-300">{notice}</p>}

      <button
        onClick={submit}
        disabled={!clip || chosen.length === 0 || submitting}
        className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : mode === 'now' ? (
          <Send className="w-4 h-4 stroke-[2.5]" />
        ) : (
          <CalendarDays className="w-4 h-4 stroke-[2.5]" />
        )}
        <span>
          {mode === 'now' ? 'Publish now' : 'Schedule'}
          {chosen.length > 0 ? ` to ${chosen.length} account${chosen.length === 1 ? '' : 's'}` : ''}
        </span>
      </button>
    </div>
  );
}

function PlatformOptions({
  platform,
  options,
  creator,
  onChange,
}: {
  platform: SocialPlatform;
  options: Options;
  creator: TikTokCreatorInfoResponse | 'error' | undefined;
  onChange: (key: string, value: unknown) => void;
}) {
  const select = 'px-2 py-1 rounded-lg bg-neutral-900 border border-neutral-800 text-[11px] text-white focus:outline-none';
  const check = 'flex items-center gap-1.5 text-[11px] text-neutral-300';

  if (platform === 'youtube') {
    return (
      <div className="space-y-2">
        <input
          value={String(options.title ?? '')}
          maxLength={100}
          onChange={(e) => onChange('title', e.target.value)}
          placeholder="YouTube title"
          className="w-full px-2 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
        />
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={String(options.privacy_status)}
            onChange={(value) => onChange('privacy_status', value)}
            options={YOUTUBE_PRIVACY_OPTIONS}
            aria-label="YouTube privacy"
            className={select}
          />
          <span className="text-[11px] text-neutral-400">Made for kids?</span>
          {[true, false].map((value) => (
            <label key={String(value)} className={check}>
              <input type="radio" checked={options.made_for_kids === value} onChange={() => onChange('made_for_kids', value)} />
              {value ? 'Yes' : 'No'}
            </label>
          ))}
        </div>
      </div>
    );
  }

  if (platform === 'tiktok') {
    if (creator === undefined) {
      return <p className="text-[11px] text-neutral-400">Loading TikTok posting options…</p>;
    }
    if (creator === 'error') {
      return <p className="text-[11px] text-rose-300">Could not load TikTok posting options. Reconnect the account and try again.</p>;
    }
    const branded = options.brand_content_toggle === true;
    const disclose = branded || options.brand_organic_toggle === true;
    return (
      <div className="space-y-2">
        <p className="text-[11px] text-neutral-400">
          Posting as <b className="text-neutral-200">{creator.nickname || creator.username}</b>
        </p>
        <Select
          value={String(options.privacy_level ?? '')}
          onChange={(value) => onChange('privacy_level', value)}
          options={creator.privacy_level_options.map((level) => ({
            value: level,
            label: TIKTOK_PRIVACY_LABELS[level] ?? level,
            disabled: branded && level === 'SELF_ONLY',
          }))}
          placeholder="Who can view this video?"
          aria-label="TikTok privacy"
          className={select}
        />
        <div className="flex flex-wrap gap-3">
          {(
            [
              ['disable_comment', 'comments', creator.comment_disabled],
              ['disable_duet', 'Duet', creator.duet_disabled],
              ['disable_stitch', 'Stitch', creator.stitch_disabled],
            ] as const
          ).map(([key, label, off]) => (
            <label key={key} className={`${check} ${off ? 'opacity-40' : ''}`}>
              <input
                type="checkbox"
                disabled={off}
                checked={!off && options[key] !== true}
                onChange={(e) => onChange(key, !e.target.checked)}
              />
              Allow {label}
            </label>
          ))}
        </div>
        <label className={check}>
          <input
            type="checkbox"
            checked={disclose}
            onChange={(e) => {
              if (!e.target.checked) {
                onChange('brand_organic_toggle', false);
                onChange('brand_content_toggle', false);
              } else {
                onChange('brand_organic_toggle', true);
              }
            }}
          />
          Disclose video content (promotes a brand, product or service)
        </label>
        {disclose && (
          <div className="flex flex-wrap gap-3 pl-5">
            <label className={check}>
              <input type="checkbox" checked={options.brand_organic_toggle === true} onChange={(e) => onChange('brand_organic_toggle', e.target.checked)} />
              Your brand
            </label>
            <label className={check}>
              <input type="checkbox" checked={branded} onChange={(e) => onChange('brand_content_toggle', e.target.checked)} />
              Branded content
            </label>
          </div>
        )}
        <p className="text-[10px] text-neutral-500">
          By posting, you agree to TikTok&apos;s{' '}
          {branded && (
            <>
              <a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noopener noreferrer" className="underline">
                Branded Content Policy
              </a>{' '}
              and{' '}
            </>
          )}
          <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener noreferrer" className="underline">
            Music Usage Confirmation
          </a>
          .
        </p>
      </div>
    );
  }

  if (platform === 'instagram') {
    return (
      <label className={check}>
        <input type="checkbox" checked={options.share_to_feed !== false} onChange={(e) => onChange('share_to_feed', e.target.checked)} />
        Also share to the main feed
      </label>
    );
  }

  return null;
}
