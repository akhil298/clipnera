"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@opencut/components/ui/button";
import { Switch } from "@opencut/components/ui/switch";
import { Textarea } from "@opencut/components/ui/textarea";
import { PanelView } from "@opencut/components/editor/panels/assets/views/base-panel";
import { cn } from "@opencut/utils/ui";
import type { PlanCard, PlanCardStep } from "@/lib/api";
import { type AiMessage, useAiStore } from "./ai-store";
import { getCurrentSync } from "./save-status";

const EXAMPLES = ["Make the title bigger", "Music a bit quieter", "Make a 30s reel of the best moments", "What did I say about pricing?"];
const STEP_ICON: Record<PlanCardStep["status"], string> = { pending: "○", running: "◐", done: "✓", failed: "✕", skipped: "–" };

/** The studio's AI tab: ask for an edit or a question about the project. */
export function AiPanel() {
	const projectId = getCurrentSync()?.getProjectId() ?? null;
	const messages = useAiStore((state) => (projectId ? state.byProject[projectId] ?? [] : []));
	const busy = useAiStore((state) => state.busy);
	const send = useAiStore((state) => state.send);
	const [draft, setDraft] = useState("");
	const end = useRef<HTMLDivElement>(null);

	useEffect(() => end.current?.scrollIntoView({ block: "end" }), [messages.length, busy]);

	if (!projectId) {
		return (
			<PanelView title="AI">
				<p className="text-muted-foreground p-2 text-sm">Open a project saved to Clipnera to use the AI.</p>
			</PanelView>
		);
	}

	const submit = () => {
		const prompt = draft.trim();
		if (!prompt || busy) return;
		setDraft("");
		void send(prompt);
	};

	return (
		<div className="flex h-full flex-col">
			<PanelView title="AI" className="min-h-0 flex-1" contentClassName="space-y-2 pb-3">
				{messages.length === 0 && (
					<div className="space-y-2 p-1">
						<p className="text-muted-foreground text-xs">
							Ask for a change, a whole edit, or a question. Select a clip or move the playhead to point at something.
						</p>
						<div className="flex flex-wrap gap-1.5">
							{EXAMPLES.map((example) => (
								<Button key={example} variant="outline" size="sm" className="h-7 text-xs" onClick={() => setDraft(example)}>
									{example}
								</Button>
							))}
						</div>
					</div>
				)}
				{messages.map((message) => (
					<Message key={message.id} message={message} />
				))}
				{busy && <p className="text-muted-foreground animate-pulse px-1 text-xs">Working…</p>}
				<div ref={end} />
			</PanelView>
			<div className="border-t p-2">
				<Textarea
					value={draft}
					onChange={(event) => setDraft(event.target.value)}
					onKeyDown={(event) => {
						if (event.key === "Enter" && !event.shiftKey) {
							event.preventDefault();
							submit();
						}
					}}
					placeholder="Ask AI to edit…"
					aria-label="Ask AI to edit"
					rows={2}
					maxLength={2000}
					className="resize-none text-sm"
				/>
				<div className="mt-1.5 flex justify-end">
					<Button size="sm" onClick={submit} disabled={busy || !draft.trim()}>
						Send
					</Button>
				</div>
			</div>
		</div>
	);
}

function Message({ message }: { message: AiMessage }) {
	const send = useAiStore((state) => state.send);
	const undo = useAiStore((state) => state.undo);
	const busy = useAiStore((state) => state.busy);
	const card = useAiStore((state) => (message.planId ? state.plans[message.planId] : undefined));
	const mine = message.role === "user";
	if (card) return <PlanCardView card={card} />;
	return (
		<div className={cn("flex", mine ? "justify-end" : "justify-start")}>
			<div
				className={cn(
					"max-w-[90%] rounded-md px-2.5 py-1.5 text-sm",
					mine ? "bg-foreground text-background" : "bg-accent text-foreground",
					message.kind === "error" && "text-destructive",
				)}
			>
				<p className="whitespace-pre-wrap">{message.kind === "edit" ? `✓ ${message.text}` : message.text}</p>
				{(message.choices?.length ?? 0) > 0 && (
					<div className="mt-1.5 flex flex-wrap gap-1">
						{message.choices!.map((choice) => (
							<Button key={choice.id} variant="outline" size="sm" className="h-6 text-xs" disabled={busy}
								onClick={() => message.prompt && void send(message.prompt, [choice.id])}>
								{choice.label}
							</Button>
						))}
					</div>
				)}
				{(message.options?.length ?? 0) > 0 && (
					<div className="mt-1.5 flex flex-wrap gap-1">
						{message.options!.map((option) => (
							<Button key={option} variant="outline" size="sm" className="h-6 text-xs" disabled={busy}
								onClick={() => void send(`${message.prompt ?? ""} — ${option}`.trim())}>
								{option}
							</Button>
						))}
					</div>
				)}
				{message.undoStepId && (
					<Button variant="text" size="sm" className="mt-1 h-5 px-0 text-xs underline" disabled={busy || message.undone}
						onClick={() => void undo(message.id)}>
						{message.undone ? "Undone" : "Undo"}
					</Button>
				)}
			</div>
		</div>
	);
}

function PlanCardView({ card }: { card: PlanCard }) {
	const { approve, reject, editPlan, control, alternative, undoStep, busy } = useAiStore();
	const [undone, setUndone] = useState<Set<string>>(new Set());
	const proposed = card.status === "proposed";
	const running = card.status === "running" || card.status === "approved";

	return (
		<div className="bg-accent/60 space-y-2 rounded-md border p-2.5 text-sm">
			<div>
				<div className="flex items-start justify-between gap-2">
					<p className="font-medium">{card.title}</p>
					<span className="text-muted-foreground shrink-0 text-[11px] uppercase">{card.status}</span>
				</div>
				<p className="text-muted-foreground text-xs">{card.summary}</p>
				<p className="mt-1 text-xs">
					{card.result_line} · up to {card.credits} credit{card.credits === 1 ? "" : "s"}
					{card.credits_charged > 0 && ` · charged ${card.credits_charged}`}
				</p>
			</div>

			<ol className="space-y-1.5">
				{card.steps.map((step) => (
					<li key={step.id} className={cn("flex gap-2", !step.enabled && "opacity-50")}>
						<span className={cn("w-3 shrink-0 text-xs", step.status === "failed" && "text-destructive",
							step.status === "running" && "animate-pulse")}>
							{STEP_ICON[step.status]}
						</span>
						<div className="min-w-0 flex-1">
							<p className="text-xs font-medium">
								{step.intent}
								{step.optional && <span className="text-muted-foreground font-normal"> (optional)</span>}
							</p>
							{step.why && <p className="text-muted-foreground text-[11px]">{step.why}</p>}
							{step.note && step.status !== "pending" && <p className="text-[11px]">{step.note}</p>}
							{step.undo_step_id && !undone.has(step.id) && !running && (
								<Button variant="text" size="sm" className="h-4 px-0 text-[11px] underline" disabled={busy}
									onClick={() => { setUndone(new Set(undone).add(step.id)); void undoStep(card.id, step.undo_step_id!); }}>
									Undo step
								</Button>
							)}
						</div>
						{proposed && (
							<Switch checked={step.enabled} disabled={busy} aria-label={`Run: ${step.intent}`}
								onCheckedChange={(on) => void editPlan(card.id, { enabled: { [step.id]: on } })} />
						)}
					</li>
				))}
			</ol>

			{card.assumptions.length > 0 && (
				<div className="text-muted-foreground text-[11px]">
					<p className="font-medium">Assumed</p>
					<ul className="list-disc pl-4">{card.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
				</div>
			)}
			{card.warnings.length > 0 && (
				<ul className="text-caution list-disc pl-4 text-[11px]">{card.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
			)}
			{card.premium.length > 0 && (
				<p className="text-[11px]">
					<span className="rounded bg-amber-500/20 px-1 text-amber-300">Premium</span> {card.premium.join(", ")} · a
					free alternative is selected; approve keeps it free
				</p>
			)}
			{card.error && <p className="text-destructive text-[11px]">{card.error}</p>}

			<div className="flex flex-wrap gap-1.5 pt-1">
				{proposed && (
					<>
						<Button size="sm" className="h-7" disabled={busy || !card.steps.some((s) => s.enabled)} onClick={() => void approve(card.id)}>
							Approve
						</Button>
						<Button size="sm" variant="outline" className="h-7" disabled={busy} onClick={() => void reject(card.id)}>
							Reject
						</Button>
						{card.runner_up_title && (
							<Button size="sm" variant="ghost" className="h-7 text-xs" disabled={busy} onClick={() => void alternative(card.id)}>
								Try the other version
							</Button>
						)}
					</>
				)}
				{running && (
					<>
						<Button size="sm" variant="outline" className="h-7" disabled={busy} onClick={() => void control(card.id, "pause")}>Pause</Button>
						<Button size="sm" variant="outline" className="h-7" disabled={busy} onClick={() => void control(card.id, "stop")}>Take over</Button>
					</>
				)}
				{card.status === "paused" && (
					<>
						<Button size="sm" className="h-7" disabled={busy} onClick={() => void control(card.id, "resume")}>Resume</Button>
						<Button size="sm" variant="outline" className="h-7" disabled={busy} onClick={() => void control(card.id, "stop")}>Stop</Button>
					</>
				)}
			</div>
		</div>
	);
}
