'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';

// The vendored OpenCut editor (frontend/opencut, MIT) needs the browser: WebCodecs, WebGPU,
// IndexedDB and WASM. Keep it out of the server render and out of every other page's bundle.
const OpenCutEditor = dynamic(
  () => import('@opencut/clipnera/editor-shell').then((m) => m.OpenCutEditor),
  { ssr: false, loading: () => <Splash label="Loading the editor…" /> },
);

// Built by frontend/opencut/tools (Tailwind v4), with its tokens scoped to .oc-root.
const EDITOR_CSS = '/opencut/editor.css';
const ROOT_CLASS = 'oc-root';

/** Loads the editor's stylesheet and scopes its tokens to <body> while the editor is open. */
function useEditorStyles(enabled: boolean): boolean {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = EDITOR_CSS;
    link.onload = () => setReady(true);
    document.head.appendChild(link);
    document.body.classList.add(ROOT_CLASS, 'dark');
    return () => {
      link.remove();
      document.body.classList.remove(ROOT_CLASS, 'dark');
      setReady(false);
    };
  }, [enabled]);

  return ready;
}

/** /studio/[projectId]: the full-screen timeline editor. "new" starts a fresh project. */
export function OpenCutStudio({ projectId }: { projectId: string }) {
  const { flags, isLoading } = useFeatureFlags();
  const stylesReady = useEditorStyles(flags.agent_editor);

  if (isLoading) return <Splash label="Loading…" />;
  if (!flags.agent_editor) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-neutral-950 text-neutral-300">
        <p className="text-sm">The editor isn&apos;t available on your account yet.</p>
        <Link href="/dashboard" className="text-sm font-semibold text-amber-400 hover:text-amber-300">
          Back to dashboard
        </Link>
      </div>
    );
  }
  if (!stylesReady) return <Splash label="Loading the editor…" />;
  return <OpenCutEditor projectId={projectId} />;
}

function Splash({ label }: { label: string }) {
  return (
    <div className="flex h-screen items-center justify-center gap-3 bg-neutral-950 text-sm text-neutral-400">
      <Loader2 className="h-5 w-5 animate-spin text-amber-400" />
      {label}
    </div>
  );
}
