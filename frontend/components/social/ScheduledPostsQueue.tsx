'use client';

import React, { useState } from 'react';
import { CalendarDays, ExternalLink, Loader2 } from 'lucide-react';
import { socialApi, type SocialPostResponse, type SocialPostStatus } from '@/lib/api';
import { formatInZone } from '@/lib/utils/timezones';
import { PLATFORM_STYLE } from './platforms';

const STATUS_STYLE: Record<SocialPostStatus, { label: string; className: string }> = {
  scheduled: { label: 'Scheduled', className: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  publishing: { label: 'Publishing…', className: 'bg-sky-500/10 text-sky-300 border-sky-500/20' },
  published: { label: 'Published', className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  failed: { label: 'Failed', className: 'bg-rose-500/10 text-rose-400 border-rose-500/20' },
  cancelled: { label: 'Cancelled', className: 'bg-neutral-800 text-neutral-400 border-neutral-700' },
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
    <div className="p-5 rounded-xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-lg">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-neutral-300 flex items-center gap-2">
          <CalendarDays className="w-4 h-4 text-amber-400" />
          <span>Scheduled Content Queue</span>
        </h3>
        <span className="text-xs font-mono text-neutral-400">{posts?.length ?? 0} posts</span>
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
            const status = STATUS_STYLE[post.status];
            return (
              <div
                key={post.id}
                className="p-3.5 rounded-lg bg-neutral-950 border border-neutral-800 space-y-2 hover:border-neutral-700 transition-all"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-[10px] px-2 py-0.5 rounded font-bold uppercase bg-neutral-800 text-white shrink-0">
                      {PLATFORM_STYLE[post.platform].name}
                    </span>
                    <span className="text-[11px] text-neutral-400 truncate">{post.account_handle}</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold border ${status.className}`}>
                    {status.label}
                  </span>
                </div>

                <h4 className="text-xs font-bold text-white line-clamp-1">{post.clip_title}</h4>
                {post.caption && <p className="text-[11px] text-neutral-400 italic line-clamp-2">&quot;{post.caption}&quot;</p>}

                {post.error_message && post.status !== 'published' && (
                  <p className={`text-[11px] ${post.status === 'failed' ? 'text-rose-300' : 'text-amber-300'}`}>
                    {post.error_message}
                  </p>
                )}

                <div className="flex items-center justify-between text-[10px] text-neutral-500 pt-1 border-t border-neutral-900 font-mono">
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
                      className="text-neutral-400 hover:text-rose-400 font-bold disabled:opacity-50"
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
    </div>
  );
}
