"use client";

import { useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { CaptionStylePreview } from "@/components/dashboard/CaptionStylePreview";
import { ProLockBadge } from "@/components/dashboard/ProLockBadge";
import { canUseCaptionStyle, useEntitlements } from "@/hooks/useEntitlements";
import { getAllCaptionStyles, resolveCaptionPreset } from "@/lib/utils/captionStyles";
import { cn } from "@opencut/utils/ui";
import type { BackendSync } from "./backend-sync";
import { useCurrentSync } from "./save-status";

const STYLES = getAllCaptionStyles();
const NO_SYNC = () => () => {};

const TILE = "relative h-16 overflow-hidden rounded-md border-[1.5px] transition-colors disabled:opacity-60";
const tileState = (active: boolean) =>
	active ? "border-primary ring-primary/25 ring-[3px]" : "hover:border-muted-foreground/40";

/** The project's caption style, or null while captions are off. */
function useCaptionStyle(sync: BackendSync | null): string | null {
	return useSyncExternalStore(
		sync ? (listener) => sync.subscribe(listener) : NO_SYNC,
		() => {
			const captions = sync?.getCaptions();
			return captions?.enabled ? resolveCaptionPreset(captions.style) : null;
		},
		() => null,
	);
}

/** Every caption style, for the Text tab: picking one captions the whole video in it on export. */
export function CaptionStyles() {
	const sync = useCurrentSync();
	const current = useCaptionStyle(sync);
	const { entitlements, promptUpgrade } = useEntitlements();
	const [saving, setSaving] = useState(false);
	if (!sync) return null;

	const pick = async (style: string | null) => {
		setSaving(true);
		try {
			await sync.setCaptionStyle(style);
		} catch (error) {
			toast.error("Couldn't change the captions", {
				description: error instanceof Error ? error.message : undefined,
			});
		} finally {
			setSaving(false);
		}
	};

	return (
		<section className="flex flex-col gap-2 pt-4">
			<div className="flex items-baseline justify-between">
				<span className="text-sm">Caption styles</span>
				<span className="text-muted-foreground text-xs">{STYLES.length} styles</span>
			</div>
			<div className="grid grid-cols-3 gap-1.5">
				<button
					type="button"
					onClick={() => void pick(null)}
					disabled={saving}
					aria-pressed={!current}
					title="Export the video without captions"
					className={cn(TILE, tileState(!current), "bg-accent text-muted-foreground text-[11px] font-semibold")}
				>
					No captions
				</button>
				{STYLES.map((style) => {
					const unlocked = canUseCaptionStyle(entitlements, style.id);
					return (
						<button
							key={style.id}
							type="button"
							onClick={() => void (unlocked ? pick(style.id) : promptUpgrade(`The ${style.name} caption style`))}
							disabled={saving}
							aria-pressed={current === style.id}
							title={style.description}
							className={cn(TILE, tileState(current === style.id))}
						>
							<CaptionStylePreview config={style.config} words={["MOST", "NEVER"]} fontSize={13} className="absolute inset-0 !rounded-none" />
							<span className="absolute inset-x-0 bottom-0 truncate bg-black/60 px-1 py-0.5 text-center text-[10px] font-semibold text-white">
								{style.name}
							</span>
							{!unlocked && <ProLockBadge feature={`The ${style.name} style`} className="absolute top-1 right-1 !px-1 !text-[9px]" />}
						</button>
					);
				})}
			</div>
		</section>
	);
}
