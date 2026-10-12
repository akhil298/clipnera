/**
 * Converts between the studio's scene (OpenCut) and Clipnera's Timeline v1, the document the
 * backend, the agent and the renderer share. See ../../BRIDGE.md for the field-by-field mapping.
 *
 * The bridge owns a few fields of each item (timing, source range, speed, volume, placement,
 * text). Everything else an element carries rides along in `item.extra.element`, and whatever the
 * backend item has that the studio doesn't (keyframes, a caption style) is kept from `base`.
 */

import type { MediaAsset } from "@opencut/media/types";
import type { ParamValues } from "@opencut/params";
import { VOLUME_DB_MAX, VOLUME_DB_MIN } from "@opencut/timeline/audio-constants";
import { buildDefaultElementParams } from "@opencut/timeline/element-utils";
import { MAIN_TRACK_NAME } from "@opencut/timeline/placement/main-track";
import type {
	AudioTrack,
	OverlayTrack,
	SceneTracks,
	TimelineElement,
	TimelineTrack,
	VideoTrack,
} from "@opencut/timeline/types";
import { generateUUID } from "@opencut/utils/id";
import { type MediaTime, roundMediaTime, TICKS_PER_SECOND } from "@opencut/wasm";
import {
	type Asset,
	type Extra,
	type Item,
	itemFrames,
	type Timeline,
	type Track,
	type TrackKind,
	type Transform,
} from "@/lib/editor/timeline";

/** The project settings a conversion needs: the backend's fps and the canvas in pixels. */
export interface Canvas {
	fps: Timeline["fps"];
	width: number;
	height: number;
}

const MAX_TEXT = 200;
const MAX_SFX_NAME = 40;
const NEW_TEXT_STYLE = "studio";
const DEFAULT_TRANSFORM: Transform = { x: 0.5, y: 0.5, scale: 1, rotation: 0 };

// Element fields the bridge maps to item fields; the rest goes into extra.element.
const OWNED_FIELDS = ["id", "startTime", "duration"] as const;
const OWNED_MEDIA_FIELDS = ["trimStart", "trimEnd", "sourceDuration", "mediaId", "buffer"] as const;
const OWNED_PARAMS = [
	"transform.positionX",
	"transform.positionY",
	"transform.scaleX",
	"transform.rotate",
	"volume",
	"content",
] as const;

export const toFrame = (ticks: number, fps: number): number =>
	Math.round((ticks * fps) / TICKS_PER_SECOND);

export const toTicks = (frames: number, fps: number): MediaTime =>
	roundMediaTime({ time: (frames * TICKS_PER_SECOND) / fps });

const round4 = (value: number) => Math.round(value * 1e4) / 1e4;
const clamp = (value: number, min: number, max: number) =>
	Math.min(max, Math.max(min, value));

// ---------------------------------------------------------------- scene -> Timeline

/**
 * The Timeline the scene amounts to. `assets` are the ones the backend has (or will, with an
 * add_asset in the same batch); an element whose media isn't among them is left out until it is.
 * `base` (the last saved Timeline) supplies captions, markers and the fields the studio doesn't edit.
 */
export function sceneToTimeline({
	tracks,
	canvas,
	assets,
	base,
}: {
	tracks: SceneTracks;
	canvas: Canvas;
	assets: Record<string, Asset>;
	base: Timeline;
}): Timeline {
	const baseItems = new Map(
		base.tracks.flatMap((track) => track.items.map((item) => [item.id, item] as const)),
	);
	const ordered: Array<[TimelineTrack, TrackKind, Extra]> = [
		...tracks.overlay.map(
			(track) => [track, overlayKind(track), overlayExtra(track)] as [TimelineTrack, TrackKind, Extra],
		),
		[tracks.main, "video", { name: tracks.main.name, role: "main" }],
		...tracks.audio.map((track) => [track, "audio", { name: track.name }] as [TimelineTrack, TrackKind, Extra]),
	];
	return {
		...base,
		fps: canvas.fps,
		width: canvas.width,
		height: canvas.height,
		assets,
		tracks: ordered.map(([track, kind, extra]) => ({
			id: track.id,
			kind,
			muted: "muted" in track ? track.muted : false,
			hidden: "hidden" in track ? track.hidden : false,
			extra,
			items: track.elements.flatMap((element) => {
				const item = elementToItem({ element, canvas, assets, base: baseItems.get(element.id) });
				return item ? [item] : [];
			}),
		})),
	};
}

function overlayKind(track: OverlayTrack): TrackKind {
	if (track.type === "video") return "overlay";
	if (track.type === "text") return "text";
	return "graphic";
}

function overlayExtra(track: OverlayTrack): Extra {
	return track.type === "graphic" || track.type === "effect"
		? { name: track.name, type: track.type }
		: { name: track.name };
}

function elementToItem({
	element,
	canvas,
	assets,
	base,
}: {
	element: TimelineElement;
	canvas: Canvas;
	assets: Record<string, Asset>;
	base: Item | undefined;
}): Item | null {
	const at = toFrame(element.startTime, canvas.fps);
	// From the rounded end, not the rounded length, so back-to-back elements never overlap by a frame.
	const frames = Math.max(1, toFrame(element.startTime + element.duration, canvas.fps) - at);
	const element_ = rest(element);

	switch (element.type) {
		case "video":
		case "image": {
			const asset = assets[element.mediaId];
			if (!asset) return null;
			const speed = element.type === "video" && element.retime ? round4(clamp(element.retime.rate, 0.25, 4)) : 1;
			return {
				...clipBase(base),
				id: element.id,
				at,
				asset: asset.id,
				...sourceRange({ asset, trimStart: element.trimStart, frames, speed, fps: canvas.fps }),
				speed,
				volume: linearVolume(element.params),
				transform: transformOf(element.params, canvas),
				extra: { element: element_ },
			};
		}
		case "audio": {
			if (element.sourceType === "library") {
				return {
					type: "sfx",
					id: element.id,
					at,
					dur: frames,
					name: (element.name || "Sound").slice(0, MAX_SFX_NAME),
					gain_db: round4(clamp(numberParam(element.params, "volume", 0), -60, 12)),
					extra: { element: element_ },
				};
			}
			const asset = assets[element.mediaId];
			if (!asset) return null;
			const speed = element.retime ? round4(clamp(element.retime.rate, 0.25, 4)) : 1;
			return {
				...clipBase(base),
				id: element.id,
				at,
				asset: asset.id,
				...sourceRange({ asset, trimStart: element.trimStart, frames, speed, fps: canvas.fps }),
				speed,
				volume: linearVolume(element.params),
				extra: { element: element_ },
			};
		}
		case "text": {
			const content = String(element.params.content ?? "");
			return {
				type: "text",
				style: base?.type === "text" ? base.style : NEW_TEXT_STYLE,
				id: element.id,
				at,
				dur: frames,
				text: content.slice(0, MAX_TEXT) || " ",
				transform: transformOf(element.params, canvas),
				extra: content.length > MAX_TEXT ? { element: element_, content } : { element: element_ },
			};
		}
		case "sticker":
		case "graphic":
		case "effect":
			return { type: "graphic", id: element.id, at, dur: frames, extra: { element: element_ } };
	}
}

function clipBase(base: Item | undefined) {
	return base?.type === "clip"
		? { ...base }
		: {
				type: "clip" as const,
				transform: { ...DEFAULT_TRANSFORM },
				keyframes: {},
				transition_in: null,
			};
}

/** Source frames a clip plays; an image plays as many as it lasts, a video never past its end. */
function sourceRange({
	asset,
	trimStart,
	frames,
	speed,
	fps,
}: {
	asset: Asset;
	trimStart: MediaTime;
	frames: number;
	speed: number;
	fps: number;
}): { src_in: number; src_out: number } {
	if (asset.kind === "image") return { src_in: 0, src_out: frames };
	// The most source frames that still play in `frames` (itemFrames rounds span / speed half up).
	const span = Math.max(1, Math.floor((frames + 0.4999) * speed));
	const src_in = clamp(toFrame(trimStart, fps), 0, Math.max(0, asset.frames - 1));
	return { src_in, src_out: Math.min(asset.frames, src_in + span) };
}

/** The element without the fields the bridge maps, safe to store as JSON. */
function rest(element: TimelineElement): Extra {
	const copy: Record<string, unknown> = { ...element };
	for (const field of OWNED_FIELDS) delete copy[field];
	if ("mediaId" in element) for (const field of OWNED_MEDIA_FIELDS) delete copy[field];
	if (element.type === "audio") delete copy.buffer;
	const params: Record<string, unknown> = { ...element.params };
	for (const key of OWNED_PARAMS) delete params[key];
	// Kept only when it differs from scaleX, which `scale` carries.
	if (params["transform.scaleY"] === element.params["transform.scaleX"]) delete params["transform.scaleY"];
	copy.params = params;
	if (copy.retime) copy.retime = { ...(copy.retime as object), rate: undefined };
	return JSON.parse(JSON.stringify(copy)) as Extra;
}

function numberParam(params: ParamValues, key: string, fallback: number): number {
	const value = params[key];
	return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function linearVolume(params: ParamValues): number {
	if (params.muted === true) return 0;
	const db = numberParam(params, "volume", 0);
	return db <= VOLUME_DB_MIN ? 0 : round4(clamp(10 ** (db / 20), 0, 2));
}

function transformOf(params: ParamValues, canvas: Canvas): Transform {
	return {
		x: round4(clamp(0.5 + numberParam(params, "transform.positionX", 0) / canvas.width, -1, 2)),
		y: round4(clamp(0.5 + numberParam(params, "transform.positionY", 0) / canvas.height, -1, 2)),
		scale: round4(clamp(numberParam(params, "transform.scaleX", 1), 0.0001, 10)),
		rotation: round4(clamp(numberParam(params, "transform.rotate", 0), -360, 360)),
	};
}

// ---------------------------------------------------------------- Timeline -> scene

/**
 * The scene a Timeline shows as. Items the studio can't show (music, sound effects made
 * elsewhere, clips whose media didn't load) are listed in `unshown`, so saving leaves them be.
 */
export function timelineToScene({
	timeline,
	media,
}: {
	timeline: Timeline;
	media: ReadonlyMap<string, MediaAsset>;
}): { tracks: SceneTracks; unshown: Set<string> } {
	const unshown = new Set<string>();
	const canvas: Canvas = { fps: timeline.fps, width: timeline.width, height: timeline.height };
	const mainTrack =
		timeline.tracks.find((t) => t.kind === "video" && t.extra.role === "main") ??
		timeline.tracks.find((t) => t.kind === "video");

	const elementsOf = (track: Track) =>
		track.items.flatMap((item) => {
			const element = itemToElement({ item, timeline, media, canvas });
			if (!element) unshown.add(item.id);
			return element ? [element] : [];
		});

	const main: VideoTrack = mainTrack
		? {
				id: mainTrack.id,
				name: String(mainTrack.extra.name ?? MAIN_TRACK_NAME),
				type: "video",
				elements: elementsOf(mainTrack) as VideoTrack["elements"],
				muted: mainTrack.muted,
				hidden: mainTrack.hidden,
			}
		: { id: generateUUID(), name: MAIN_TRACK_NAME, type: "video", elements: [], muted: false, hidden: false };

	const overlay: OverlayTrack[] = [];
	const audio: AudioTrack[] = [];
	for (const track of timeline.tracks) {
		if (track === mainTrack) continue;
		const name = String(track.extra.name ?? defaultTrackName(track.kind));
		const elements = elementsOf(track);
		if (track.kind === "audio") {
			audio.push({ id: track.id, name, type: "audio", elements: elements as AudioTrack["elements"], muted: track.muted });
		} else if (track.kind === "text") {
			overlay.push({ id: track.id, name, type: "text", elements: elements as never, hidden: track.hidden });
		} else if (track.kind === "graphic") {
			const type = track.extra.type === "effect" ? "effect" : "graphic";
			overlay.push({ id: track.id, name, type, elements: elements as never, hidden: track.hidden });
		} else {
			overlay.push({ id: track.id, name, type: "video", elements: elements as never, muted: track.muted, hidden: track.hidden });
		}
	}
	return { tracks: { overlay, main, audio }, unshown };
}

function defaultTrackName(kind: TrackKind): string {
	return { video: "Video", overlay: "Video", text: "Text", audio: "Audio", graphic: "Graphics" }[kind];
}

function itemToElement({
	item,
	timeline,
	media,
	canvas,
}: {
	item: Item;
	timeline: Timeline;
	media: ReadonlyMap<string, MediaAsset>;
	canvas: Canvas;
}): TimelineElement | null {
	const stored = (item.extra.element ?? null) as Record<string, unknown> | null;
	const timing = {
		id: item.id,
		startTime: toTicks(item.at, canvas.fps),
		duration: toTicks(itemFrames(item), canvas.fps),
	};

	switch (item.type) {
		case "clip": {
			const asset = timeline.assets[item.asset];
			const file = media.get(item.asset);
			if (!asset || !file) return null;
			const sourceDuration = asset.kind === "image" ? timing.duration : toTicks(asset.frames, canvas.fps);
			const trimStart = toTicks(asset.kind === "image" ? 0 : item.src_in, canvas.fps);
			const used = toTicks(item.src_out - item.src_in, canvas.fps);
			const trimEnd = roundMediaTime({ time: Math.max(0, sourceDuration - trimStart - (asset.kind === "image" ? timing.duration : used)) });
			const type = asset.kind;
			const params = {
				...buildDefaultElementParams({ type }),
				...((stored?.params as ParamValues | undefined) ?? {}),
				...volumeParams(item.volume),
				...(type === "audio" ? {} : transformParams(item.transform, canvas, stored)),
			};
			const retime = item.speed === 1 ? undefined : { ...((stored?.retime as object) ?? {}), rate: item.speed };
			const element = {
				...(type === "video" ? { isSourceAudioEnabled: true, hidden: false } : {}),
				...stored,
				...timing,
				type,
				name: String(stored?.name ?? file.name),
				mediaId: asset.id,
				trimStart,
				trimEnd,
				sourceDuration,
				params,
				...(type === "image" ? {} : { retime }),
				...(type === "audio" ? { sourceType: "upload" } : {}),
			};
			return element as TimelineElement;
		}
		case "text": {
			const full = typeof item.extra.content === "string" && item.extra.content.startsWith(item.text) ? item.extra.content : item.text;
			return {
				...stored,
				...timing,
				type: "text",
				name: String(stored?.name ?? "Text"),
				trimStart: roundMediaTime({ time: 0 }),
				trimEnd: roundMediaTime({ time: 0 }),
				params: {
					...buildDefaultElementParams({ type: "text" }),
					...((stored?.params as ParamValues | undefined) ?? {}),
					content: full,
					...transformParams(item.transform, canvas, stored),
				},
			} as TimelineElement;
		}
		case "graphic":
			return stored ? ({ ...stored, ...timing } as TimelineElement) : null;
		case "sfx":
			// Only sounds added in the studio carry their library URL.
			return stored
				? ({
						...stored,
						...timing,
						name: stored.name ?? item.name,
						params: { ...((stored.params as ParamValues | undefined) ?? {}), volume: item.gain_db },
					} as unknown as TimelineElement)
				: null;
		case "music":
			return null;
	}
}

function volumeParams(volume: number): ParamValues {
	if (volume <= 0) return { volume: VOLUME_DB_MIN, muted: true };
	return { volume: clamp(round4(20 * Math.log10(volume)), VOLUME_DB_MIN, VOLUME_DB_MAX), muted: false };
}

function transformParams(transform: Transform, canvas: Canvas, stored: Record<string, unknown> | null): ParamValues {
	const storedScaleY = ((stored?.params ?? {}) as ParamValues)["transform.scaleY"];
	return {
		"transform.positionX": round4((transform.x - 0.5) * canvas.width),
		"transform.positionY": round4((transform.y - 0.5) * canvas.height),
		"transform.scaleX": transform.scale,
		"transform.scaleY": typeof storedScaleY === "number" ? storedScaleY : transform.scale,
		"transform.rotate": transform.rotation,
	};
}

/** The Timeline asset for a media file uploaded under `key`. */
export function assetFor({ media, key, fps }: { media: MediaAsset; key: string; fps: number }): Asset {
	return {
		id: media.id,
		kind: media.type,
		key,
		proxy: null,
		frames: media.type === "image" ? 1 : Math.max(1, Math.round((media.duration ?? 0) * fps)),
		width: media.width ?? null,
		height: media.height ?? null,
		has_audio: media.type === "audio" || (media.type === "video" && media.hasAudio !== false),
	};
}
