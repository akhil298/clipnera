"use client";

import { useEffect, useRef, useState } from "react";
import { AiMagicIcon, ArrowRight01Icon, ArrowUp02Icon, Attachment01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Button } from "@opencut/components/ui/button";
import { Switch } from "@opencut/components/ui/switch";
import { Textarea } from "@opencut/components/ui/textarea";
import { cn } from "@opencut/utils/ui";
import type { PlanCard, PlanCardStep } from "@/lib/api";
import { takeStudioHandoff } from "@/lib/editor/handoff";
import { type AiMessage, useAiStore } from "./ai-store";
import { type FootageFile, useFootageStore, watchFootage } from "./footage";
import { useCurrentSync } from "./save-status";

const EXAMPLES = ["Make the title bigger", "Music a bit quieter", "Make a 30s reel of the best moments", "What did I say about pricing?"];
const FILE_TYPES = "video/mp4,video/quicktime,video/webm,image/*,audio/*";
const FILE_BAR: Record<FootageFile["state"], string> = {
	uploading: "bg-primary",
	saving: "bg-primary",
	waiting: "bg-primary/60 animate-pulse",
	understanding: "bg-primary animate-pulse",
	ready: "bg-constructive",
	failed: "bg-destructive",
	upload_failed: "bg-destructive",
};
// One list for "no messages yet": a new array each render would re-render the chat forever.
const NO_MESSAGES: AiMessage[] = [];
const STEP_ICON: Record<PlanCardStep["status"], string> = { pending: "○", running: "◐", done: "✓", failed: "✕", skipped: "–" };

/** The studio's AI chat: drop files in, ask for an edit, or ask about the project. */
export function AiPanel({ onCollapse }: { onCollapse?: () => void }) {
	const sync = useCurrentSync();
	const projectId = sync?.getProjectId() ?? null;
	const messages = useAiStore((state) => (projectId && state.byProject[projectId]) || NO_MESSAGES);
	const busy = useAiStore((state) => state.busy);
	const auto = useAiStore((state) => state.auto);
	const setAuto = useAiStore((state) => state.setAuto);
	const files = useFootageStore((state) => state.files);
	const held = useFootageStore((state) => state.held);
	const addFiles = useFootageStore((state) => state.add);
	const ask = useFootageStore((state) => state.ask);
	const [draft, setDraft] = useState("");
	const [dragging, setDragging] = useState(false);
	const end = useRef<HTMLDivElement>(null);
	const picker = useRef<HTMLInputElement>(null);

	useEffect(() => {
		// In braces: newer Chrome returns a promise from scrollIntoView, and an effect must not.
		end.current?.scrollIntoView({ block: "end" });
	}, [messages.length, busy, files.length]);

	useEffect(() => {
		if (!sync) return;
		const stop = watchFootage(sync);
		// Files and a prompt handed over by the Editor home's "start" box.
		const handoff = takeStudioHandoff(sync.getProjectId());
		if (handoff) {
			void useFootageStore.getState().add(handoff.files).then(() => {
				if (handoff.prompt) useFootageStore.getState().ask(handoff.prompt);
			});
		}
		return stop;
	}, [sync]);

	const working = files.some((file) => file.state !== "ready" && file.state !== "failed" && file.state !== "upload_failed");
	const status = busy ? "Working on it…" : working ? "Going through your files…" : "Ready when you are";

	const submit = () => {
		const prompt = draft.trim();
		if (!prompt || busy || held) return;
		setDraft("");
		ask(prompt);
	};

	return (
		<div
			className={cn("panel ai-panel bg-background flex h-full flex-col overflow-hidden border", dragging && "ring-primary ring-2")}
			onDragOver={(event) => {
				if (!projectId || !event.dataTransfer.types.includes("Files")) return;
				event.preventDefault();
				setDragging(true);
			}}
			onDragLeave={() => setDragging(false)}
			onDrop={(event) => {
				if (!projectId || !event.dataTransfer.files.length) return;
				event.preventDefault();
				// The timeline and media panel have their own drop handling.
				event.stopPropagation();
				setDragging(false);
				void addFiles([...event.dataTransfer.files]);
			}}
		>
			<header className="flex h-14 shrink-0 items-center gap-2.5 border-b px-3">
				<span className="ai-sheen flex size-8 items-center justify-center rounded-lg shadow-md" aria-hidden>
					<HugeiconsIcon icon={AiMagicIcon} className="size-4" />
				</span>
				<div className="min-w-0 flex-1">
					<p className="text-sm leading-tight font-semibold">Clipnera AI</p>
					<p className="text-muted-foreground flex items-center gap-1.5 text-[0.68rem] leading-tight" role="status">
						<span className={cn("size-1.5 rounded-full", busy || working ? "bg-primary animate-pulse" : "bg-constructive")} aria-hidden />
						{projectId ? status : "No project open"}
					</p>
				</div>
				{projectId && (
					<label className="text-muted-foreground flex cursor-pointer items-center gap-1.5 text-[0.68rem]"
						title="Auto: the AI edits on its own, with no questions and no approval step. Off: it shows a plan and waits for you.">
						Auto
						<Switch checked={auto} onCheckedChange={setAuto} aria-label="Auto mode" />
					</label>
				)}
				{onCollapse && (
					<Button variant="text" size="icon" aria-label="Hide the AI chat" onClick={onCollapse}>
						<HugeiconsIcon icon={ArrowRight01Icon} />
					</Button>
				)}
			</header>

			{!projectId ? (
				<p className="text-muted-foreground p-4 text-sm">Open a project saved to Clipnera to use the AI.</p>
			) : (
				<>
					<div className="scrollbar-hidden min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
						{files.length > 0 && <Files files={files} />}
						{messages.length === 0 && (
							<div className="ai-rise space-y-3 pt-1">
								{files.length === 0 && (
									<button
										type="button"
										onClick={() => picker.current?.click()}
										className="hover:border-primary/60 hover:bg-primary/5 flex w-full flex-col items-center gap-1.5 rounded-xl border border-dashed px-3 py-6 text-center transition-colors"
									>
										<span className="bg-accent flex size-9 items-center justify-center rounded-full">
											<HugeiconsIcon icon={Attachment01Icon} className="size-4" />
										</span>
										<span className="text-sm font-medium">Drop your videos, music and images</span>
										<span className="text-muted-foreground text-xs">I&apos;ll go through them and tell you what I found</span>
									</button>
								)}
								<p className="text-muted-foreground px-0.5 text-xs">
									{auto
										? "Auto is on: once I've gone through your files I'll make a first edit myself. Or tell me what you want."
										: "Ask for a change, a whole edit, or a question. Select a clip or move the playhead to point at something."}
								</p>
								<div className="flex flex-wrap gap-1.5">
									{EXAMPLES.map((example) => (
										<button key={example} type="button" onClick={() => setDraft(example)}
											className="bg-accent/60 hover:bg-accent hover:border-primary/40 rounded-full border px-3 py-1.5 text-xs transition-colors">
											{example}
										</button>
									))}
								</div>
							</div>
						)}
						{messages.map((message) => (
							<Message key={message.id} message={message} />
						))}
						{(busy || held) && (
							<div className="text-muted-foreground flex items-center gap-2 px-1 text-xs">
								<span className="flex gap-1" aria-hidden>
									<span className="bg-primary size-1.5 animate-bounce rounded-full" />
									<span className="bg-primary size-1.5 animate-bounce rounded-full [animation-delay:120ms]" />
									<span className="bg-primary size-1.5 animate-bounce rounded-full [animation-delay:240ms]" />
								</span>
								{busy ? "Working…" : "Going through your files first…"}
							</div>
						)}
						<div ref={end} />
					</div>

					<div className="shrink-0 p-3 pt-1">
						<div className="bg-accent/50 focus-within:border-primary/60 rounded-2xl border p-2 transition-colors">
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
								className="resize-none border-0 bg-transparent px-1.5 text-sm shadow-none focus-visible:ring-0"
							/>
							<div className="mt-1 flex items-center justify-between">
								<input
									ref={picker}
									type="file"
									multiple
									accept={FILE_TYPES}
									className="hidden"
									onChange={(event) => {
										void addFiles([...(event.target.files ?? [])]);
										event.target.value = "";
									}}
								/>
								<Button variant="ghost" size="sm" className="text-muted-foreground rounded-full" onClick={() => picker.current?.click()}>
									<HugeiconsIcon icon={Attachment01Icon} />
									Attach
								</Button>
								<button
									type="button"
									aria-label="Send"
									onClick={submit}
									disabled={busy || Boolean(held) || !draft.trim()}
									className="ai-sheen flex size-8 items-center justify-center rounded-full shadow-md transition-opacity disabled:opacity-35"
								>
									<HugeiconsIcon icon={ArrowUp02Icon} className="size-4" />
								</button>
							</div>
						</div>
					</div>
				</>
			)}
		</div>
	);
}

/** Each file of the project and how far the AI has got with it. */
function Files({ files }: { files: FootageFile[] }) {
	const retry = useFootageStore((state) => state.retry);
	return (
		<ul className="max-h-48 space-y-1.5 overflow-y-auto" aria-label="Your files">
			{files.map((file) => (
				<li key={file.id} className="bg-accent/50 rounded-xl border px-2.5 py-2">
					<div className="flex items-baseline gap-2 text-xs">
						<span className="min-w-0 flex-1 truncate font-medium" title={file.name}>{file.name}</span>
						<span className={cn("shrink-0 text-[0.68rem]", file.state === "ready" ? "text-constructive" : "text-muted-foreground")}>
							{file.state === "ready" ? "✓ Ready" : file.detail}
						</span>
						{file.canRetry && (
							<Button variant="text" size="sm" className="h-4 px-0 text-[11px] underline" onClick={() => void retry(file.id)}>
								Retry
							</Button>
						)}
					</div>
					{file.state !== "ready" && (
						<div className="bg-muted/50 mt-1.5 h-1 overflow-hidden rounded-full" aria-hidden>
							<div className={cn("h-full rounded-full transition-[width] duration-500", FILE_BAR[file.state])}
								style={{ width: `${Math.max(6, Math.round(file.progress * 100))}%` }} />
						</div>
					)}
				</li>
			))}
		</ul>
	);
}

function Message({ message }: { message: AiMessage }) {
	const send = useAiStore((state) => state.send);
	const undo = useAiStore((state) => state.undo);
	const busy = useAiStore((state) => state.busy);
	const ask = useFootageStore((state) => state.ask);
	const card = useAiStore((state) => (message.planId ? state.plans[message.planId] : undefined));
	const mine = message.role === "user";
	if (card) return <PlanCardView card={card} />;
	return (
		<div className={cn("ai-rise flex", mine ? "justify-end" : "justify-start")}>
			<div
				className={cn(
					"max-w-[92%] px-3 py-2 text-sm leading-relaxed",
					mine ? "ai-sheen rounded-2xl rounded-br-md font-medium" : "bg-accent/70 text-foreground rounded-2xl rounded-bl-md border",
					message.kind === "error" && "text-destructive",
				)}
			>
				<p className="whitespace-pre-wrap">{message.kind === "edit" ? `✓ ${message.text}` : message.text}</p>
				{(message.choices?.length ?? 0) > 0 && (
					<div className="mt-1.5 flex flex-wrap gap-1">
						{message.choices!.map((choice) => (
							<Button key={choice.id} variant="outline" size="sm" className="h-auto rounded-full px-3 py-1 text-left text-xs whitespace-normal" disabled={busy}
								onClick={() => message.prompt && void send(message.prompt, [choice.id])}>
								{choice.label}
							</Button>
						))}
					</div>
				)}
				{(message.options?.length ?? 0) > 0 && (
					<div className="mt-1.5 flex flex-wrap gap-1">
						{message.options!.map((option) => (
							<Button key={option} variant="outline" size="sm" className="h-auto rounded-full px-3 py-1 text-left text-xs whitespace-normal" disabled={busy}
								onClick={() => void send(`${message.prompt ?? ""} — ${option}`.trim())}>
								{option}
							</Button>
						))}
					</div>
				)}
				{(message.suggestions?.length ?? 0) > 0 && (
					<div className="mt-1.5 flex flex-wrap gap-1">
						{message.suggestions!.map((suggestion) => (
							<Button key={suggestion} variant="outline" size="sm" className="h-auto rounded-full px-3 py-1 text-left text-xs whitespace-normal" disabled={busy}
								onClick={() => ask(suggestion)}>
								{suggestion}
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
		<div className="ai-rise bg-accent/60 border-primary/25 space-y-2 rounded-2xl border p-3 text-sm">
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
