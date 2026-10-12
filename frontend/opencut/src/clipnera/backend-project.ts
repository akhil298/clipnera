/**
 * Opens a Clipnera editor project in the studio: the Timeline comes from /editor/projects/{id},
 * becomes an OpenCut scene (bridge.ts), and BackendSync saves every change back.
 */

import { DEFAULT_BACKGROUND_COLOR } from "@opencut/background/color";
import type { EditorCore } from "@opencut/core";
import type { TProject } from "@opencut/project/types";
import { CURRENT_PROJECT_VERSION } from "@opencut/services/storage/migrations";
import { buildDefaultScene, getProjectDurationFromScenes } from "@opencut/timeline/scenes";
import { editorApi } from "@/lib/api";
import { normalise } from "@/lib/editor/timeline";
import { BackendSync } from "./backend-sync";
import { timelineToScene } from "./bridge";
import { loadMedia } from "./media";

/** `/studio/new` makes a backend project; any other id is one. */
export const NEW_PROJECT_ID = "new";

export async function createBackendProject(): Promise<string> {
	return (await editorApi.create({})).id;
}

export async function openBackendProject({
	editor,
	projectId,
}: {
	editor: EditorCore;
	projectId: string;
}): Promise<BackendSync> {
	const response = await editorApi.get(projectId);
	const timeline = normalise(response.timeline);
	const media = await loadMedia({
		projectId,
		assets: Object.values(timeline.assets),
		urls: response.asset_urls,
	});
	const { tracks, unshown } = timelineToScene({ timeline, media });
	const scene = { ...buildDefaultScene({ name: "Main scene", isMain: true }), tracks };
	const size = { width: timeline.width, height: timeline.height };

	const project: TProject = {
		metadata: {
			id: response.id,
			name: response.title,
			duration: getProjectDurationFromScenes({ scenes: [scene] }),
			createdAt: new Date(response.created_at),
			updatedAt: new Date(response.updated_at),
		},
		scenes: [scene],
		currentSceneId: scene.id,
		settings: {
			fps: { numerator: timeline.fps, denominator: 1 },
			canvasSize: size,
			canvasSizeMode: "custom",
			lastCustomCanvasSize: size,
			originalCanvasSize: null,
			background: { type: "color", color: DEFAULT_BACKGROUND_COLOR },
		},
		version: CURRENT_PROJECT_VERSION,
	};
	await editor.project.openRemoteProject({ project, mediaAssets: [...media.values()] });

	const sync = new BackendSync(editor, projectId, response.version, timeline, unshown);
	sync.start();
	return sync;
}
