'use client';

import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { adminUsersApi, AdminClip, AdminProjectClipsResponse } from '@/lib/api';
import { AdminError, AdminSpinner } from './AdminUi';

function formatSeconds(seconds: number): string {
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function ClipCard({ clip }: { clip: AdminClip }) {
  const [captioned, setCaptioned] = useState(Boolean(clip.captioned_video_url));
  const src = captioned ? clip.captioned_video_url : clip.video_url;
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-950 overflow-hidden flex flex-col">
      {src ? (
        <video
          key={src}
          src={src}
          poster={clip.poster_url ?? undefined}
          controls
          preload="none"
          className="w-full aspect-[9/16] bg-black object-contain"
        />
      ) : (
        <div className="w-full aspect-[9/16] grid place-items-center text-xs text-neutral-500">No video stored</div>
      )}
      <div className="p-3 space-y-1.5 text-xs">
        <p className="font-bold text-white line-clamp-2" title={clip.title}>{clip.title}</p>
        <p className="text-neutral-400">
          {formatSeconds(clip.duration_seconds)} · score {Math.round(clip.score)} · {clip.status}
        </p>
        <div className="flex gap-3">
          {clip.captioned_video_url && clip.video_url && (
            <button type="button" onClick={() => setCaptioned((on) => !on)} className="font-bold text-amber-300 hover:text-amber-200">
              {captioned ? 'Show raw cut' : 'Show captioned'}
            </button>
          )}
          {src && (
            <a href={src} target="_blank" rel="noopener noreferrer" className="font-bold text-neutral-300 hover:text-white">
              Open
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

/** The source video and every clip of one user's project, playable in place. */
export function AdminProjectClips({ userId, projectId, onClose }: { userId: string; projectId: string; onClose: () => void }) {
  const [data, setData] = useState<AdminProjectClipsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    adminUsersApi
      .getProjectClips(userId, projectId)
      .then(setData)
      .catch((err: Error) => setError(err.message || 'Could not load the clips'));
  }, [userId, projectId]);

  return (
    <div className="rounded-2xl border border-neutral-800 bg-neutral-900/90 p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-white">{data?.title ?? 'Clips'}</p>
          <p className="text-xs text-neutral-500">Links expire after a while; reopen to refresh them.</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close clips" className="text-neutral-400 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>
      {error && <AdminError message={error} />}
      {!data && !error && <AdminSpinner />}
      {data && (
        <>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-neutral-400">Source video</p>
            {data.source_video_url ? (
              <video src={data.source_video_url} controls preload="none" className="w-full max-w-xl rounded-xl bg-black" />
            ) : (
              <p className="text-xs text-neutral-500">Not stored.</p>
            )}
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-neutral-400">Clips ({data.clips.length})</p>
            {data.clips.length === 0 ? (
              <p className="text-xs text-neutral-500">No clips were made for this project.</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {data.clips.map((clip) => (
                  <ClipCard key={clip.id} clip={clip} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
