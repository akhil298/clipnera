/**
 * A Clipnera project's media in the studio. Each file's OpenCut media id is its Timeline asset id.
 * The browser keeps a copy of every file it has had (OpenCut's media storage, per project), so
 * a project opens without downloading; anything missing comes from the asset's signed URL.
 */

import { toast } from "sonner";
import { processMediaAssets } from "@opencut/media/processing";
import type { MediaAsset } from "@opencut/media/types";
import { storageService } from "@opencut/services/storage/service";
import type { Asset } from "@/lib/editor/timeline";

const PARALLEL_DOWNLOADS = 3;

export async function loadMedia({
	projectId,
	assets,
	urls,
	have = [],
}: {
	projectId: string;
	assets: Asset[];
	urls: Record<string, string>;
	have?: MediaAsset[];
}): Promise<Map<string, MediaAsset>> {
	const wanted = new Set(assets.map((asset) => asset.id));
	const media = new Map(have.filter((m) => wanted.has(m.id)).map((m) => [m.id, m] as const));
	if (media.size < wanted.size) {
		const cached = await storageService.loadAllMediaAssets({ projectId }).catch(() => [] as MediaAsset[]);
		for (const m of cached) if (wanted.has(m.id) && !media.has(m.id)) media.set(m.id, m);
	}

	const missing = assets.filter((asset) => !media.has(asset.id) && urls[asset.id]);
	for (let i = 0; i < missing.length; i += PARALLEL_DOWNLOADS) {
		const batch = missing.slice(i, i + PARALLEL_DOWNLOADS);
		const loaded = await Promise.all(batch.map((asset) => download(projectId, asset, urls[asset.id])));
		for (const m of loaded) if (m) media.set(m.id, m);
	}
	return media;
}

async function download(projectId: string, asset: Asset, url: string): Promise<MediaAsset | null> {
	const name = asset.key.split("/").pop() || asset.id;
	try {
		const response = await fetch(url);
		if (!response.ok) throw new Error(`Download failed (${response.status})`);
		const blob = await response.blob();
		const file = new File([blob], name, { type: blob.type || guessType(asset) });
		const [processed] = await processMediaAssets({ files: [file] });
		if (!processed) return null;
		const media: MediaAsset = { ...processed, id: asset.id };
		// Cache it for next time; a full browser store only costs a re-download.
		await storageService.saveMediaAsset({ projectId, mediaAsset: media }).catch(() => undefined);
		return media;
	} catch (error) {
		toast.error(`Couldn't load ${name}`, { description: error instanceof Error ? error.message : undefined });
		return null;
	}
}

function guessType(asset: Asset): string {
	return { video: "video/mp4", image: "image/jpeg", audio: "audio/mpeg" }[asset.kind];
}
