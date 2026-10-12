"use client";

import { useEffect, useState } from "react";
import { Button } from "@opencut/components/ui/button";
import { rendersApi, type RenderStatus } from "@/lib/api";
import { getCurrentSync } from "./save-status";

const POLL_MS = 2000;

/** "Render on server", under the studio's own Export: renders the saved project at full size. */
export function ServerRender() {
	const sync = getCurrentSync();
	const [render, setRender] = useState<RenderStatus | null>(null);
	const [error, setError] = useState<string | null>(null);
	const projectId = sync?.getProjectId();

	useEffect(() => {
		if (!projectId || !render || render.status === "done" || render.status === "failed") return;
		const timer = setTimeout(() => {
			rendersApi.get(projectId, render.id).then(setRender).catch((e) => setError(e instanceof Error ? e.message : "Lost the render"));
		}, POLL_MS);
		return () => clearTimeout(timer);
	}, [projectId, render]);

	if (!sync || !projectId) return null;

	const start = async () => {
		setError(null);
		try {
			await sync.flush();
			setRender(await rendersApi.start(projectId));
		} catch (e) {
			setError(e instanceof Error ? e.message : "Couldn't start the render");
		}
	};

	const working = render && (render.status === "queued" || render.status === "rendering");
	return (
		<div className="space-y-1.5 px-3 pb-3">
			{render?.status === "done" && render.download_url ? (
				<Button asChild variant="outline" className="w-full">
					<a href={render.download_url}>Download server render</a>
				</Button>
			) : (
				<Button variant="outline" className="w-full" disabled={!!working} onClick={() => void start()}>
					{working ? `${render.stage}…` : "Render on server"}
				</Button>
			)}
			<p className="text-muted-foreground text-[11px]">
				Renders the saved project in Clipnera at full quality, with captions and music mixed.
			</p>
			{(error || render?.error) && <p className="text-destructive text-[11px]">{error || render?.error}</p>}
		</div>
	);
}
