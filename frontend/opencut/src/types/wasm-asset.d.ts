// next.config.mjs serves opencut-wasm's .wasm as a file; importing it gives its URL.
declare module "opencut-wasm/opencut_wasm_bg.wasm" {
	const url: string;
	export default url;
}

declare module "opencut-wasm/opencut_wasm_bg.js" {
	export * from "opencut-wasm";
	export function __wbg_set_wasm(exports: WebAssembly.Exports): void;
}
