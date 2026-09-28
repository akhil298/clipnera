'use client';

import React, { useState } from 'react';
import { CalendarDays, ExternalLink, Loader2 } from 'lucide-react';
import { socialApi, type SocialPostResponse, type SocialPostStatus } from '@/lib/api';
import { formatInZone } from '@/lib/utils/timezones';
import { PLATFORM_STYLE } from './platforms';
import { StatusPill, type StatusTone } from '@/components/ui/StatusPill';

const STATUS: Record<SocialPostStatus, { label: string; tone: StatusTone }> = {
  scheduled: { label: 'Scheduled', tone: 'scheduled' },
  publishing: { label: 'Publishing…', tone: 'processing' },
  published: { label: 'Published', tone: 'ready' },
  failed: { label: 'Failed', tone: 'failed' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
};

interface ScheduledPostsQueueProps {
  posts: SocialPostResponse[] | null;
  timeZone: string;
  onChanged: () => void;
}

/** The user's posts with live status, post links and failure reasons. */
export function ScheduledPostsQueue({ posts, timeZone, onChanged }: ScheduledPostsQueueProps) {
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cancel = async (postId: string) => {
    setCancelling(postId);
    setError(null);
    try {
      await socialApi.cancelPost(postId);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel the post');
    } finally {
      setCancelling(null);
    }
  };

  return (
    <section className="p-4 sm:p-5 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-4" aria-labelledby="queue-title">
      <div className="flex items-center justify-between">
        <h2 id="queue-title" className="text-sm font-bold text-white flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-amber-400" />
          Queue
        </h2>
        <span className="text-xs text-neutral-500 tabular-nums">{posts?.length ?? 0} posts</span>
      </div>

      {error && <p className="text-[11px] text-rose-300">{error}</p>}

      {posts === null ? (
        <div className="flex items-center gap-2 text-xs text-neutral-400">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading posts…
        </div>
      ) : posts.length === 0 ? (
        <p className="text-xs text-neutral-500">Nothing scheduled yet. Published and scheduled posts appear here.</p>
      ) : (
        <div className="space-y-3">
          {posts.map((post) => {
            const status = STATUS[post.status];
            return (
              <div
                key={post.id}
                className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2 hover:border-neutral-700 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`w-6 h-6 rounded-md bg-gradient-to-br ${PLATFORM_STYLE[post.platform].color} flex items-center justify-center text-[9px] font-extrabold text-white shrink-0`} title={PLATFORM_STYLE[post.platform].name}>
                      {PLATFORM_STYLE[post.platform].short}
                    </span>
                    <span className="text-[11px] text-neutral-400 truncate">{post.account_handle}</span>
                  </div>
                  <StatusPill tone={status.tone}>{status.label}</StatusPill>
                </div>

                <h3 className="text-[13px] font-semibold text-white line-clamp-1">{post.clip_title}</h3>
                {post.caption && <p className="text-[11px] text-neutral-400 italic line-clamp-2">&quot;{post.caption}&quot;</p>}

                {post.error_message && post.status !== 'published' && (
                  <p className={`text-[11px] ${post.status === 'failed' ? 'text-rose-300' : 'text-amber-300'}`}>
                    {post.error_message}
                  </p>
                )}

                <div className="flex items-center justify-between text-[11px] text-neutral-500 pt-2 border-t border-neutral-900">
                  <span className="text-neutral-300">
                    {formatInZone(post.published_at ?? post.scheduled_at, timeZone)}
                  </span>
                  {post.post_url ? (
                    <a
                      href={post.post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 font-bold inline-flex items-center gap-1 hover:underline"
                    >
                      View post <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : post.status === 'scheduled' ? (
                    <button
                      onClick={() => cancel(post.id)}
                      disabled={cancelling !== null}
                      className="text-neutral-400 hover:text-rose-300 font-semibold disabled:opacity-50"
                    >
                      {cancelling === post.id ? 'Cancelling…' : 'Cancel'}
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
