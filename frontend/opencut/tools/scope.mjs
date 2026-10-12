// Scope the built stylesheet to the editor: tokens Tailwind and OpenCut put on :root/:host,
// and OpenCut's dark tokens on .dark, move to .oc-root, so the editor's variables never
// override Clipnera's (Clipnera's <html> already carries .dark).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const [input, output] = process.argv.slice(2);
const css = readFileSync(input, "utf8")
	.replaceAll(":root,:host", ".oc-root")
	.replaceAll(":root", ".oc-root")
	.replaceAll(".dark{", ".oc-root.dark{")
	.replaceAll(".dark .panel{", ".oc-root.dark .panel{");
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, css);
