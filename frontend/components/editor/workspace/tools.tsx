import { AudioLines, Captions, Crop, Film, Music2, Sparkles, Type } from 'lucide-react';
import type { ReactNode } from 'react';

/** The editor's tools (02-editor §6–§9). Each opens the left panel; the panel units fill it by id. */
export type EditorToolId = 'transcript' | 'captions' | 'hook' | 'broll' | 'audio' | 'format' | 'sound';

export interface EditorTool {
  id: EditorToolId;
  label: string;
  icon: ReactNode;
  /** ⌥1–⌥7, in `aria-keyshortcuts` form. */
  shortcut: string;
}

export const EDITOR_TOOLS: ReadonlyArray<EditorTool> = [
  { id: 'transcript', label: 'Transcript', icon: <Type />, shortcut: 'Alt+1' },
  { id: 'captions', label: 'Captions', icon: <Captions />, shortcut: 'Alt+2' },
  { id: 'hook', label: 'Hook', icon: <Sparkles />, shortcut: 'Alt+3' },
  { id: 'broll', label: 'B-roll', icon: <Film />, shortcut: 'Alt+4' },
  { id: 'audio', label: 'Audio', icon: <AudioLines />, shortcut: 'Alt+5' },
  { id: 'format', label: 'Format', icon: <Crop />, shortcut: 'Alt+6' },
  { id: 'sound', label: 'Sound', icon: <Music2 />, shortcut: 'Alt+7' },
];

export const toolLabel = (id: EditorToolId): string => EDITOR_TOOLS.find((tool) => tool.id === id)?.label ?? id;
