"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react-oc";
import { EditorCore } from "@opencut/core";
import { useEditor } from "@opencut/editor/use-editor";
import { useKeybindingsListener } from "@opencut/actions/use-keybindings";
import { useKeybindingsStore } from "@opencut/actions/keybindings-store";
import { useTimelineStore } from "@opencut/timeline/timeline-store";
import { useEditorActions } from "@opencut/actions/use-editor-actions";
import { loadFontAtlas } from "@opencut/fonts/google-fonts";
import {
	initializeGpuRenderer,
	isGpuAvailable,
} from "@opencut/services/renderer/gpu-renderer";
import {
	createBackendProject,
	NEW_PROJECT_ID,
	openBackendProject,
} from "@opencut/clipnera/backend-project";
import type { BackendSync } from "@opencut/clipnera/backend-sync";
import { setCurrentSync } from "@opencut/clipnera/save-status";
import { ApiError } from "@/lib/api";

interface EditorProviderProps {
	projectId: string;
	children: React.ReactNode;
}

export function EditorProvider({ projectId, children }: EditorProviderProps) {
	const activeProject = useEditor((e) => e.project.getActiveOrNull());
	const router = useRouter();
	const [isLoading, setIsLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const { setLoadingProject } = useKeybindingsStore();

	useEffect(() => {
		setLoadingProject(isLoading);
	}, [isLoading, setLoadingProject]);

	useEffect(() => {
		let cancelled = false;
		let sync: BackendSync | null = null;
		const editor = EditorCore.getInstance();

		// Clipnera: projects live on the server (clipnera/backend-project.ts), not in browser storage.
		const loadProject = async () => {
			try {
				setIsLoading(true);
				if (projectId === NEW_PROJECT_ID) {
					const newProjectId = await createBackendProject();
					if (!cancelled) router.replace(`/studio/${newProjectId}`);
					return;
				}
				await initializeGpuRenderer();
				editor.renderer.setDegraded(!isGpuAvailable());
				sync = await openBackendProject({ editor, projectId });

				if (cancelled) {
					sync.stop();
					return;
				}
				setCurrentSync(sync);
				setIsLoading(false);
				loadFontAtlas();
			} catch (err) {
				if (cancelled) return;
				const wasmPanic = (window as Window & { __wasmPanic?: string }).__wasmPanic;
				if (wasmPanic) {
					delete (window as Window & { __wasmPanic?: string }).__wasmPanic;
					setError(wasmPanic);
				} else if (err instanceof ApiError && err.status === 404) {
					setError("This project doesn't exist, or isn't yours.");
				} else {
					setError(err instanceof Error ? err.message : "Failed to load project");
				}
				setIsLoading(false);
			}
		};

		loadProject();

		return () => {
			cancelled = true;
			setCurrentSync(null);
			const closing = sync;
			void closing?.flush().finally(() => closing.stop());
		};
	}, [projectId, router]);

	if (error) {
		return (
			<div className="bg-background flex h-screen w-screen items-center justify-center">
				<div className="flex flex-col items-center gap-4">
					<p className="text-destructive text-sm">{error}</p>
				</div>
			</div>
		);
	}

	if (isLoading) {
		return (
			<div className="bg-background flex h-screen w-screen items-center justify-center">
				<div className="flex flex-col items-center gap-4">
					<Loader2 className="text-muted-foreground size-8 animate-spin" />
					<p className="text-muted-foreground text-sm">Loading project...</p>
				</div>
			</div>
		);
	}

	if (!activeProject) {
		return (
			<div className="bg-background flex h-screen w-screen items-center justify-center">
				<div className="flex flex-col items-center gap-4">
					<Loader2 className="text-muted-foreground size-8 animate-spin" />
					<p className="text-muted-foreground text-sm">Exiting project...</p>
				</div>
			</div>
		);
	}

	return (
		<>
			<EditorRuntimeBindings />
			{children}
		</>
	);
}

function EditorRuntimeBindings() {
	const editor = useEditor();
	const rippleEditingEnabled = useTimelineStore(
		(state) => state.rippleEditingEnabled,
	);

	useEffect(() => {
		editor.command.isRippleEnabled = rippleEditingEnabled;
	}, [editor, rippleEditingEnabled]);

	useEffect(() => {
		const handleBeforeUnload = (event: BeforeUnloadEvent) => {
			if (!editor.save.getIsDirty()) return;
			event.preventDefault();
			(event as unknown as { returnValue: string }).returnValue = "";
		};

		window.addEventListener("beforeunload", handleBeforeUnload);
		return () => window.removeEventListener("beforeunload", handleBeforeUnload);
	}, [editor]);

	useEditorActions();
	useKeybindingsListener();
	return null;
}
