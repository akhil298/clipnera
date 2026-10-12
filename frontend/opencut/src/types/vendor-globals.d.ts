// Ambient types the vendored editor needs that TypeScript's DOM lib and the packages don't ship.

declare module "soundtouchjs";

interface EyeDropperResult {
	sRGBHex: string;
}

interface EyeDropper {
	open(options?: { signal?: AbortSignal }): Promise<EyeDropperResult>;
}

declare var EyeDropper: {
	prototype: EyeDropper;
	new (): EyeDropper;
};
