"use client";

import { useSyncExternalStore } from "react";
import type { BackendSync, SyncStatus } from "./backend-sync";

// The open project's sync, for the header's save dot; one studio is open at a time.
let current: BackendSync | null = null;
const listeners = new Set<() => void>();
let unsubscribe: (() => void) | null = null;

const notify = () => {
	for (const listener of listeners) listener();
};

/** The open project's sync, or null outside a Clipnera project. */
export function getCurrentSync(): BackendSync | null {
	return current;
}

export function setCurrentSync(sync: BackendSync | null): void {
	unsubscribe?.();
	current = sync;
	unsubscribe = sync ? sync.subscribe(notify) : null;
	notify();
}

function useSaveStatus(): SyncStatus | null {
	return useSyncExternalStore(
		(listener) => {
			listeners.add(listener);
			return () => listeners.delete(listener);
		},
		() => current?.getStatus() ?? null,
		() => null,
	);
}

const LOOK: Record<SyncStatus, { label: string; dot: string }> = {
	saved: { label: "Saved", dot: "bg-emerald-500" },
	saving: { label: "Saving…", dot: "bg-amber-400 animate-pulse" },
	offline: { label: "Offline", dot: "bg-muted-foreground" },
	error: { label: "Not saved", dot: "bg-destructive" },
};

/** "Saved / Saving… / Offline" next to Export, for a project saved to Clipnera. */
export function SaveStatus() {
	const status = useSaveStatus();
	if (!status) return null;
	const { label, dot } = LOOK[status];
	return (
		<span className="text-muted-foreground flex items-center gap-1.5 text-xs" role="status" aria-live="polite">
			<span className={`size-2 rounded-full ${dot}`} aria-hidden />
			{label}
		</span>
	);
}
