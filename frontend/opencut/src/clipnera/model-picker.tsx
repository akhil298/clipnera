"use client";

import { useEffect, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@opencut/components/ui/select";
import { type AiEffort, type AiModels, editorApi } from "@/lib/api";
import { useAiStore } from "./ai-store";

// Radix Select can't hold an empty value: this stands for "the default".
const DEFAULT = "default";
const EFFORT_LABEL: Record<AiEffort, string> = { low: "Low", medium: "Medium", high: "High", xhigh: "Extra high" };
const TRIGGER = "text-muted-foreground h-7 w-auto gap-1 rounded-full border-0 bg-transparent px-2 text-xs shadow-none";

let offered: Promise<AiModels> | null = null;

/** The model and reasoning effort the AI chat's next prompts run on. */
export function ModelPicker({ disabled }: { disabled?: boolean }) {
	const model = useAiStore((state) => state.model);
	const effort = useAiStore((state) => state.effort);
	const setModel = useAiStore((state) => state.setModel);
	const setEffort = useAiStore((state) => state.setEffort);
	const [choices, setChoices] = useState<AiModels | null>(null);

	useEffect(() => {
		offered ??= editorApi.models();
		offered.then(setChoices, () => {
			offered = null;
		});
	}, []);

	// A model this browser saved that the server no longer offers.
	useEffect(() => {
		if (choices && model && !choices.models.includes(model)) setModel(null);
	}, [choices, model, setModel]);

	if (!choices) return null;
	return (
		<div className="flex items-center">
			<Select value={model ?? DEFAULT} onValueChange={(value) => setModel(value === DEFAULT ? null : value)} disabled={disabled}>
				<SelectTrigger className={TRIGGER} aria-label="AI model" title="The model the AI edits with">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					<SelectItem value={DEFAULT}>{choices.default_model}</SelectItem>
					{choices.models
						.filter((name) => name !== choices.default_model)
						.map((name) => (
							<SelectItem key={name} value={name}>
								{name}
							</SelectItem>
						))}
				</SelectContent>
			</Select>
			<Select
				value={effort ?? DEFAULT}
				onValueChange={(value) => setEffort(value === DEFAULT ? null : (value as AiEffort))}
				disabled={disabled}
			>
				<SelectTrigger className={TRIGGER} aria-label="Reasoning effort" title="How hard the AI thinks before it edits">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					<SelectItem value={DEFAULT}>Auto effort</SelectItem>
					{choices.efforts.map((name) => (
						<SelectItem key={name} value={name}>
							{EFFORT_LABEL[name]}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		</div>
	);
}
