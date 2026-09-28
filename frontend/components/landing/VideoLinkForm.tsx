'use client';

import { Scissors } from 'lucide-react';

interface VideoLinkFormProps {
  id: string;
  url: string;
  setUrl: (url: string) => void;
  onSubmit: () => void;
}

/** Paste a long video's link and start cutting. */
export function VideoLinkForm({ id, url, setUrl, onSubmit }: VideoLinkFormProps) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="flex flex-col gap-2 rounded-2xl border border-neutral-800 bg-neutral-900 p-1.5 sm:flex-row"
    >
      <label htmlFor={id} className="sr-only">
        Link to your long video
      </label>
      <input
        id={id}
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="Paste a YouTube link…"
        className="h-12 min-w-0 flex-1 rounded-xl bg-transparent px-3.5 text-[15px] text-white placeholder-neutral-500 focus:outline-none"
      />
      <button
        type="submit"
        className="flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-amber-500 px-5 text-[15px] font-bold text-neutral-950 transition-colors hover:bg-amber-400 active:scale-[0.98]"
      >
        <Scissors className="h-4 w-4" aria-hidden="true" />
        Cut my clips
      </button>
    </form>
  );
}
