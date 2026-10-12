// Stands in for the opencut-wasm package entry (next.config.mjs aliases "opencut-wasm" here).
// The package is a wasm-bindgen "bundler" build that imports its .wasm file directly, which
// webpack's WebAssembly parser can't read (it uses newer WASM features). So the .wasm is
// served as a plain file and instantiated by the browser, then handed to the same JS glue.
import * as bindings from "opencut-wasm/opencut_wasm_bg.js";
import wasmUrl from "opencut-wasm/opencut_wasm_bg.wasm";

const { instance } = await WebAssembly.instantiateStreaming(fetch(wasmUrl), {
	"./opencut_wasm_bg.js": bindings,
});
bindings.__wbg_set_wasm(instance.exports);
(instance.exports.__wbindgen_start as () => void)();

export {
	TICKS_PER_SECOND,
	applyEffectPasses,
	applyMaskFeather,
	floorToFrame,
	formatTimecode,
	getCompositorCanvas,
	getLastFrameProfile,
	guessTimecodeFormat,
	initCompositor,
	initializeGpu,
	isFrameAligned,
	lastFrameTime,
	mediaTimeAdd,
	mediaTimeClamp,
	mediaTimeFromFrame,
	mediaTimeFromSeconds,
	mediaTimeMax,
	mediaTimeMin,
	mediaTimeSub,
	mediaTimeToFrame,
	mediaTimeToSeconds,
	parseTimecode,
	releaseTexture,
	renderFrame,
	resizeCompositor,
	roundToFrame,
	snappedSeekTime,
	uploadTexture,
} from "opencut-wasm/opencut_wasm_bg.js";
