'use client';

import React, { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { SocialPostResponse, SocialPostStatus } from '@/lib/api';
import { parseApiDate } from '@/lib/utils/dates';
import { PLATFORM_STYLE } from './platforms';

interface PostCalendarProps {
  posts: SocialPostResponse[] | null;
  timeZone: string;
}

const DAY_MS = 86_400_000;

/** "YYYY-MM-DD" for the calendar day `date` falls on in `timeZone`. */
const dayKey = (date: Date, timeZone: string) =>
  new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);

const STATUS_STYLE: Record<SocialPostStatus, string> = {
  scheduled: 'border-sky-500/60 bg-sky-500/10 text-sky-100',
  publishing: 'border-amber-500/60 bg-amber-500/10 text-amber-100',
  published: 'border-emerald-500/60 bg-emerald-500/10 text-emerald-100',
  failed: 'border-rose-500/60 bg-rose-500/10 text-rose-100',
  cancelled: 'border-neutral-700 bg-neutral-800/60 text-neutral-400 line-through',
};

/**
 * A week of posts, one column per day in the audience's timezone. Built from
 * the same posts list as the queue; no extra requests.
 */
export function PostCalendar({ posts, timeZone }: PostCalendarProps) {
  const [weekOffset, setWeekOffset] = useState(0);

  const days = useMemo(() => {
    // Noon UTC of "today in the zone" keeps day arithmetic clear of DST edges.
    const today = dayKey(new Date(), timeZone);
    const start = new Date(`${today}T12:00:00Z`).getTime() + weekOffset * 7 * DAY_MS;
    return Array.from({ length: 7 }, (_, i) => {
      const date = new Date(start + i * DAY_MS);
      const key = date.toISOString().slice(0, 10);
      return {
        key,
        isToday: key === today,
        weekday: date.toLocaleDateString(undefined, { weekday: 'short', timeZone: 'UTC' }),
        day: date.getUTCDate(),
        month: date.toLocaleDateString(undefined, { month: 'short', timeZone: 'UTC' }),
      };
    });
  }, [timeZone, weekOffset]);

  const byDay = useMemo(() => {
    const groups = new Map<string, SocialPostResponse[]>();
    (posts ?? []).forEach((post) => {
      const key = dayKey(parseApiDate(post.published_at || post.scheduled_at), timeZone);
      groups.set(key, [...(groups.get(key) ?? []), post]);
    });
    groups.forEach((list) =>
      list.sort((a, b) => parseApiDate(a.scheduled_at).getTime() - parseApiDate(b.scheduled_at).getTime()),
    );
    return groups;
  }, [posts, timeZone]);

  const timeOf = (post: SocialPostResponse) =>
    parseApiDate(post.published_at || post.scheduled_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', timeZone });

  const rangeLabel = `${days[0].day} ${days[0].month} – ${days[6].day} ${days[6].month}`;
  const weekCount = days.reduce((n, d) => n + (byDay.get(d.key)?.length ?? 0), 0);

  return (
    <section className="rounded-2xl bg-neutral-900/80 border border-neutral-800 p-3 sm:p-4 space-y-3" aria-labelledby="calendar-title">
      <div className="flex items-center gap-2">
        <h2 id="calendar-title" className="text-sm font-bold text-white">
          {weekOffset === 0 ? 'Next 7 days' : rangeLabel}
        </h2>
        <span className="text-xs text-neutral-500 tabular-nums">
          {weekCount} post{weekCount === 1 ? '' : 's'}
        </span>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => setWeekOffset((w) => w - 1)}
          className="h-8 w-8 flex items-center justify-center rounded-lg border border-neutral-800 text-neutral-300 hover:bg-neutral-800"
          aria-label="Previous week"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        {weekOffset !== 0 && (
          <button type="button" onClick={() => setWeekOffset(0)} className="h-8 px-2.5 rounded-lg border border-neutral-800 text-xs font-semibold text-neutral-300 hover:bg-neutral-800">
            Today
          </button>
        )}
        <button
          type="button"
          onClick={() => setWeekOffset((w) => w + 1)}
          className="h-8 w-8 flex items-center justify-center rounded-lg border border-neutral-800 text-neutral-300 hover:bg-neutral-800"
          aria-label="Next week"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0 [scrollbar-width:thin]">
        <ol className="grid grid-cols-[repeat(7,minmax(128px,1fr))] gap-2 min-w-0">
          {days.map((day) => {
            const dayPosts = byDay.get(day.key) ?? [];
            return (
              <li
                key={day.key}
                className={`rounded-xl border p-2 min-h-[132px] flex flex-col gap-1.5 ${
                  day.isToday ? 'border-amber-500/40 bg-amber-500/[0.04]' : 'border-neutral-800 bg-neutral-950/40'
                }`}
                aria-label={`${day.weekday} ${day.day} ${day.month}, ${dayPosts.length} posts`}
              >
                <div className="flex items-baseline gap-1.5 px-0.5">
                  <span className={`text-[11px] font-semibold ${day.isToday ? 'text-amber-300' : 'text-neutral-500'}`}>{day.weekday}</span>
                  <span className={`text-sm font-bold tabular-nums ${day.isToday ? 'text-amber-200' : 'text-neutral-200'}`}>{day.day}</span>
                </div>
                {dayPosts.length === 0 ? (
                  <span className="text-[11px] text-neutral-700 px-0.5">—</span>
                ) : (
                  dayPosts.map((post) => (
                    <div
                      key={post.id}
                      className={`rounded-lg border-l-[3px] px-2 py-1.5 text-[11px] leading-tight ${STATUS_STYLE[post.status]}`}
                      title={`${PLATFORM_STYLE[post.platform].name} · ${post.account_handle ?? ''} · ${post.status}`}
                    >
                      <span className="flex items-center gap-1 font-semibold tabular-nums">
                        <span className={`inline-block w-1.5 h-1.5 rounded-full bg-gradient-to-r ${PLATFORM_STYLE[post.platform].color}`} />
                        {timeOf(post)} · {PLATFORM_STYLE[post.platform].short}
                      </span>
                      <span className="block truncate opacity-90">{post.clip_title}</span>
                    </div>
                  ))
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
