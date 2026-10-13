/**
 * The Sounds tab, on Clipnera's own sound library (backend GET /editor/sounds) instead of
 * Freesound. Returns the shape OpenCut's sound views read from their old search response.
 */

import type { SoundEffect } from "@opencut/sounds/types";
import { apiUrl, type LibrarySound, soundsApi } from "@/lib/api";

export interface SoundPage {
	results: SoundEffect[];
	next: string | null;
	count: number;
}

/** A stable number for a library id: OpenCut keys sounds by numeric (Freesound) ids. */
function numericId(id: string): number {
	let hash = 0;
	for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0;
	return Math.abs(hash);
}

function toSoundEffect(sound: LibrarySound): SoundEffect {
	const url = apiUrl(sound.url);
	return {
		id: numericId(sound.id), name: sound.name, description: [sound.category, ...sound.tags].join(", "), url, previewUrl: url,
		downloadUrl: url, duration: sound.seconds, filesize: 0, type: "wav", channels: 2, bitrate: 0, bitdepth: 16,
		samplerate: 48000, username: "Clipnera", tags: sound.tags, license: sound.licence, created: "",
		downloads: 0, rating: 0, ratingCount: 0,
	};
}

export async function searchSounds({ q = "", page = 1, pageSize = 50 }: { q?: string; page?: number; pageSize?: number }): Promise<SoundPage> {
	const response = await soundsApi.search({ q, page, page_size: pageSize });
	return { results: response.results.map(toSoundEffect), next: response.has_more ? String(page + 1) : null, count: response.count };
}
