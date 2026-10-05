# Wave 6 — UI catalog (`components/ui`)

Date: 4 October 2026. Every shared primitive, with its one-line API. Import from the barrel:

```ts
import { Button, DataTable, Sidebar } from '@/components/ui';
```

Conventions all components share (match them in screen code):
- Plain function components; React 19 `ref` as a prop where a DOM ref matters (no `forwardRef`).
- `className` is merged last with `cx()` from `lib/design/styles.ts`; `focusRing` / `focusWithinRing` for focus.
- Stateful parts take `value` / `defaultValue` / `onValueChange` (or `open` / `onOpenChange`, `checked` / `onCheckedChange`) through `useControllableState`.
- Sizes are `sm | md | lg` (32 / 36 / 44 px). Tones: `neutral | accent | success | danger | info` (alerts use `warning` for amber).
- Motion goes through `motionPreset` / `collapseTransition` / `motion-safe:`; everything is instant under reduced motion.
- `cn-*` tokens only. Live demos of every state: `/design-system` (dev only).

Legend: **new** = added in Wave 6. *legacy* = old-UI file kept for `app/dashboard`; new screens use the successor named.

## Actions and inputs

| Component | API |
|---|---|
| `Button`, `buttonClasses`, `LoadingSweep` | `<Button variant="primary\|secondary\|ghost\|danger" size leadingIcon trailingIcon loading loadingLabel fullWidth>`; `buttonClasses({variant,size})` for a `<Link>` |
| `IconButton` | `<IconButton label icon variant size pressed loading tooltip>` — `label` is required (name + tooltip) |
| `Chip` | `<Chip selected? icon size="sm\|md">` — `selected` set = toggle (`aria-pressed`), unset = action chip |
| `SegmentedControl` | `<SegmentedControl label options={[{value,label,ariaLabel?,disabled?}]} value onValueChange size>` (radio group) |
| `Field` | `<Field label hint error required id>{({inputId, describedBy}) => control}</Field>` |
| `Input` | `<Input label hint error size leading trailing ...inputProps>` |
| `Textarea` | `<Textarea label hint error minRows maxRows showCount maxLength ...>` (autosizes) |
| `Checkbox` | `<Checkbox label description indeterminate error ...inputProps>` (native) |
| `Switch` | `<Switch label description checked onCheckedChange labelPosition hideLabel disabled>` |
| **`SearchField`** | `<SearchField value onValueChange label? loading shortcut={['/']} onSearch size>` — Escape clears, Clear button, `role="search"` |
| **`NumberField`** | `<NumberField label value onValueChange min max step unit allowEmpty size error>` — −/+ buttons, ↑↓, Shift ×10, clamps on blur; `null` = empty |
| **`Slider`** | `<Slider label value onValueChange min max step formatValue hint hideLabel showValue disabled>` — `role="slider"`, pointer + keys |
| **`RangeSlider`** | `<RangeSlider label value={[lo,hi]} onValueChange min max step minGap thumbLabels formatValue>` — thumbs never cross |
| **`ColorSwatchPicker`**, `TOKEN_SWATCHES` | `<ColorSwatchPicker label value onValueChange swatches? allowCustom customLabel hint>` — token hues only; `allowCustom` adds a brand-colour swatch with picker + hex field |
| **`FileDropzone`** | `<FileDropzone title hint accept multiple maxSize onFiles onReject error disabled disabledReason compact icon>` — real file input inside; rejects by type/size with a reason |
| `Select` *legacy* | Old-token dropdown. Spec 02 §3.5 rebuild still open; use `Menu` or `SegmentedControl` meanwhile |

## Overlays

| Component | API |
|---|---|
| `Menu` | `<Menu trigger={(props) => <IconButton {...props}/>} items={MenuEntry[]} side align>`; entries: item `{id,label,icon,shortcut,danger,disabled,checked,onSelect}`, `separator`, `label` |
| `Popover` | `<Popover trigger title|label open onOpenChange side align>{content or (close) => …}</Popover>` |
| `Tooltip` | `<Tooltip content side asLabel disabled>{focusable}</Tooltip>` |
| `Dialog` | `<Dialog open onOpenChange title description footer size="sm\|md\|lg" role="dialog\|alertdialog" dismissible initialFocusRef>` (bottom sheet on phones) |
| `Drawer` | `<Drawer open onOpenChange title description footer side="right\|left\|bottom" size>` |
| `ModalLayer`, `ModalHeader`, `ModalFooter` | The modal engine behind Dialog/Drawer/CommandMenu (portal, scrim, trap, Escape, scroll lock) |
| `Toast`: `ToastProvider`, `useToast` | `useToast().show({title, description, tone, action, duration})` → id; `.dismiss(id)` |
| **`CommandMenu`** | `<CommandMenu open onOpenChange groups={CommandGroup[]} onSelect query? onQueryChange? filter loading placeholder label emptyText header keepOpen>` — ⌘K modal combobox (bind the key in the shell) |
| **`CommandList`**, `useCommandList`, `filterCommandGroups`, `commandOptionId` | Inline palette parts for your own input (PromptBar slash menu): `const list = useCommandList(groups, query, onSelect)` → `{groups, activeId, setActiveId, onKeyDown, select}`; render `<CommandList id label groups activeId onActiveChange onChoose query loading emptyText>` and put `role="combobox" aria-controls aria-activedescendant={commandOptionId(id, activeId)}` on the input |
| `Portal`, `useIsClient` | Render into `document.body` after hydration |

## App shell (new)

| Component | API |
|---|---|
| **`Sidebar`** | `<Sidebar label="Main" collapsed onCollapsedChange header footer fullHeight>` — 240 px or 64 px rail; add `hidden md:flex` at the call site; persist `collapsed` with `usePersistentState` |
| **`SidebarSection`** | `<SidebarSection title?>` items `</SidebarSection>` (title hidden in the rail) |
| **`SidebarNavItem`**, `useSidebarCollapsed` | `<SidebarNavItem label icon href? onClick? active count trailing disabled>` — `aria-current="page"`; rail shows tooltip, count becomes a dot |
| **`TopBar`** | `<TopBar start end sticky variant="app\|editor">{middle}</TopBar>` — 56 px header, `z-cn-sticky` |
| **`Breadcrumbs`** | `<Breadcrumbs items={[{label, href?}]}/>` — back link to parent on phones |
| **`MobileTabBar`** | `<MobileTabBar label items={[{id,label,icon,href?,onClick?,count?}]} activeId placement="fixed\|inline">` — ≤ 5 tabs, < md; page needs `pb-16` |
| **`ResizablePanels`** | `<ResizablePanels panels={[{id,label,defaultSize,minSize,maxSize,children}]} direction storageKey>` — separators: drag, ←/→ (Shift 10%), Home/End, Enter/double-click resets; sizes persist per browser |
| **`Avatar`**, `initialsOf` | `<Avatar name src size={24\|32\|40} shape="person\|workspace" labelled status>` — initials fallback, broken-image safe |
| **`AvatarMenu`** | `<AvatarMenu name detail src items={MenuEntry[]} compact side align>` — account button + Menu |
| **`Wordmark`** | `<Wordmark size="sm\|md" markOnly>` — the brand lock-up (DS-1), decorative; wrap in a link named "Clipnera home" |
| `LogoMark` | `<LogoMark size>` — mark only |
| `PageHeader` *legacy* | Old-palette page title; new screens compose `text-cn-title-lg` heading + actions (successor still to build with Wave 6 screens) |

## Display and feedback

| Component | API |
|---|---|
| `Card`, `CardHeader`, `CardFooter`, `cardLinkOverlay` | `<Card padding interactive selected>`; one inner link gets `cardLinkOverlay` for whole-card click |
| `Badge`, `StatusBadge` | `<Badge tone dot pulse icon>`; `<StatusBadge status="processing\|ready\|failed\|scheduled\|paused\|draft">` |
| `StatusPill` *legacy* | Successor: `StatusBadge` |
| `NotWiredBadge` *legacy* | Old-UI "not connected" marker |
| `Tabs`, `TabList`, `Tab`, `TabPanel` | `<Tabs defaultValue variant="underline\|pill"><TabList label><Tab value/></TabList><TabPanel value/></Tabs>` |
| `Skeleton`, `SkeletonText`, `SkeletonGroup` | Blocks are silent; wrap in `<SkeletonGroup label="Loading projects">` (one live region) |
| `EmptyState` | `<EmptyState icon title description action secondaryAction size="compact\|default" level>` |
| `ProgressBar` | `<ProgressBar label value? max valueText tone size hideLabel>` — no value = indeterminate sweep |
| `ProgressSteps` | `<ProgressSteps label steps={[{id,label,description,status}]} orientation>` — fixed processes |
| `Kbd` | `<Kbd keys={['⌘','K']}/>` |
| `WorkingText` | `<WorkingText>Trimming 14 silences</WorkingText>` — the spinner replacement |
| **`Spinner`** | `<Spinner label size showLabel>` — only for waits with no nameable step (OAuth hand-off) |
| **`InlineAlert`** | `<InlineAlert tone="neutral\|info\|warning\|danger\|success" title action onDismiss live="alert\|status">{text}` — stays in content |
| **`Banner`** | `<Banner tone title action onDismiss live sticky>{text}` — full-width strip under the top bar (`z-cn-banner`) |
| **`Disclosure`** | `<Disclosure title summary open onOpenChange defaultOpen level variant="plain\|card" disabled>{content}` — button in heading |
| **`Accordion`** | `<Accordion items={[{id,title,summary,content,disabled}]} type="single\|multiple" value onValueChange level>` |
| **`CopyField`** | `<CopyField value label|ariaLabel hint mono masked onCopied>` — "Copied" for 2 s; falls back to select + ⌘C hint |
| **`TimeCode`** | `<TimeCode seconds total? hours fps tone="default\|muted\|inherit">` — mono, tabular, spoken as words |
| **`DataTable`** | `<DataTable caption columns={[{key,header,render,numeric,sortable,hideHeader,primary,hideOnMobile,className}]} rows getRowId getRowLabel sort onSortChange selectedIds onSelectionChange loading loadingRows empty activeId virtualize scrollClassName>` — sticky header, stacked cards < md; `virtualize` windows rows with `@tanstack/react-virtual` (desktop table) |
| **`Pagination`**, `pageWindow` | `<Pagination page pageCount? hasNext? onPageChange label loading>` — numbered, or cursor mode without `pageCount` |
| **`StatCard`** | `<StatCard label value={string\|null} delta={{value,direction,good,period}} hint chart tone loading emptyText>` — `null` shows "—", never a fake number |
| **`Sparkline`** | `<Sparkline data={number[]} label="…in words" tone="accent\|neutral\|success\|danger" area className="h-8">` (recharts, `role="img"`) |
| **`UploadProgressItem`** | `<UploadProgressItem name meta status="queued\|uploading\|paused\|processing\|done\|failed" percent eta step error thumbnail onCancel onPause onResume onRetry onDismiss action>` |
| `ScoreRing` *legacy* | Successor: `ScoreBadge` |

## Media (new)

| Component | API |
|---|---|
| **`VideoThumb`**, `ASPECT_CLASS` | `<VideoThumb poster aspect="9:16\|16:9\|1:1" duration score previewSrc previewing onScrub topLeft topRight bottomLeft dimmed selected rounded>` — decorative; the card's link names the video; hover preview after 150 ms, never under reduced motion; `onScrub(0–1)` is the sprite/seek hook |
| **`ScoreBadge`** | `<ScoreBadge score>` — amber ≥ 85, emerald ≥ 70, neutral below; number always shown |
| **`MediaGrid`** | `<MediaGrid label items getKey renderItem aspect loading skeletonCount empty>` — responsive columns, arrow keys between tiles, skeleton tiles in one live region |

Compose a clip/library tile as in the gallery's `MediaSection`: `VideoThumb` + a title `<button|Link className={cardLinkOverlay}>` + a `Checkbox` (`relative z-cn-raised`) in `topLeft`.

## Prompt and agent

| Component | API |
|---|---|
| `PromptBar` | `<PromptBar value onValueChange onSubmit mode onModeChange running onStop contexts onRemoveContext onAttach creditCost queueCount size="hero\|docked" label ref>` |
| `ContextChip` | `<ContextChip context={{id,kind,label,meta,thumbnailUrl}} onRemove>` |
| `ChoiceCard` | `<ChoiceCard question choices onChoose onSkip chosenId>` |
| `StepList` | `<StepList steps={RunStep[]} elapsed expanded onExpandedChange onRetryStep>` |
| `ResultMessage` | `<ResultMessage status summary changes notDone safeNote version onRetry suggestions onSuggestion details timestamp>` (now uses FollowUpChips) |
| **`StreamingText`** | `<StreamingText text streaming onTimecode onCitation size>` — Markdown-lite (paragraphs, `###`, lists, fenced code, bold, italic, `code`, http(s) links); `1:05` → seek button, `[n]` → CitationMarker; word groups fade 120 ms; sentences only under reduced motion |
| **`SourceCard`**, `Source` | `<SourceCard source={{id,title,kind:'clip'\|'broll'\|'transcript'\|'web',origin,snippet,thumbnail,href\|onOpen}} index variant="card\|row" highlighted>` |
| **`SourceList`** | `<SourceList sources maxVisible label highlightedId>` — horizontal strip, "+N more" |
| **`CitationMarker`** | `<CitationMarker index onClick>` — inline `[n]` button |
| **`FollowUpChips`** | `<FollowUpChips items={(string\|{id,label,icon})[]} onPick variant="chips\|list" label showLabel max loading>` — fills the bar, never sends |

## Helpers in `lib/design` (new this wave)

| Helper | Use |
|---|---|
| `usePersistentState(key, default)` | Per-browser state (sidebar collapsed, panel sizes); SSR-safe, storage errors swallowed |
| `useHoverIntent(delayMs?, enabled?)` | `{active, handlers}` for hover/focus previews; off under reduced motion |
| `useListNavigation(ids, onChoose)` | `aria-activedescendant` keyboard state for any combobox |
| `useCopyToClipboard()` | `{state: 'idle'\|'copied'\|'failed', copy(text) → Promise<boolean>}` |
| `timecode.ts` | `formatTimecode(s, {hours,fps,total})`, `parseTimecode`, `spokenDuration`, `isoDuration` (tested) |
| `markdownLite.ts` | `parseMarkdownLite`, `parseInline`, `completedSentences` (tested; produces no HTML) |

## Still to build (not in this pass)

RadioGroup (02 §3.8, mock in `libraries/_components/Additions.tsx`), Select rebuild (§3.5), CreditMeter (DS-4), ActivityIndicator (§4.8), PromptBar `modes`/`onDropFile`/`footer` (DS-9), SelectionBar (DS-13), PromptQueue, VersionHistory item, VideoPlayer chrome, Timeline.
