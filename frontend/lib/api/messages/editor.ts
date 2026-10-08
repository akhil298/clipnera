/**
 * Editor copy for error codes (frontend.md §3.3): what happened, what is safe, one action.
 * Sentence case, Indian English, first person for Clipnera. The server's `message` is a fallback only.
 * Import-free, so `node --test` can check it.
 */

export type EditorAction = 'retry' | 'reload' | 'back_to_latest' | 'add_credits' | 'contact_support' | 'replace_file' | 'none';

export interface EditorMessage {
  text: string;
  action: EditorAction;
}

const MESSAGES: Record<string, EditorMessage> = {
  // Network and saving
  NETWORK: { text: 'Not saved. Check your connection. Your next change will retry.', action: 'retry' },
  TIMEOUT: { text: 'Not saved. The server took too long. Your edit is kept on this device.', action: 'retry' },
  STALE_VERSION: { text: 'This project changed while you were editing. I caught up and kept your edits.', action: 'none' },
  NOT_FOUND: { text: "Project not found. It may have been deleted, or it's in a workspace you're not in.", action: 'none' },
  NOT_READY: { text: "This reel has no edit to open yet. Try again once its plan is ready.", action: 'retry' },
  FEATURE_DISABLED: { text: "The editor isn't on for your account yet. Your clips are in Projects.", action: 'none' },
  READ_ONLY: { text: 'You are viewing an earlier version. Go back to the latest to edit.', action: 'back_to_latest' },
  LOCKED: { text: 'Clipnera is working on this. It unlocks when the step ends.', action: 'none' },
  // Timeline rules (lib/editor/timeline.ts TimelineError codes)
  OVERLAP: { text: "That would overlap another item on this track. Move it to a free spot.", action: 'none' },
  OUT_OF_RANGE: { text: "That's past the end of the video it comes from.", action: 'none' },
  WRONG_TRACK: { text: "That can't go on this track.", action: 'none' },
  WRONG_ITEM_TYPE: { text: "That only works on video clips.", action: 'none' },
  UNKNOWN_ITEM: { text: 'That item is no longer in the project.', action: 'none' },
  UNKNOWN_TRACK: { text: 'That track is no longer in the project.', action: 'none' },
  UNKNOWN_ASSET: { text: 'That media is no longer in the project.', action: 'none' },
  DUPLICATE_ID: { text: "That's already in the project.", action: 'none' },
  BAD_PATCH: { text: "That change doesn't fit this item.", action: 'none' },
  ASSET_NOT_AVAILABLE: { text: "That clip isn't available any more. Pick another one.", action: 'none' },
  // Runs and versions
  INSUFFICIENT_CREDITS: { text: "You don't have enough credits for this edit. Nothing was charged.", action: 'add_credits' },
  RUN_NOT_QUEUED: { text: 'That edit has already started. Use Stop instead.', action: 'none' },
  UNDO_WOULD_DISCARD: { text: 'Undo would also remove hand edits made after this run.', action: 'none' },
  MEDIA_UNREADABLE: { text: "I couldn't read that file. Convert it to MP4 (H.264) and replace it.", action: 'replace_file' },
  SECOND_FAILURE: { text: "That didn't work twice. Try saying it a different way, or contact us.", action: 'contact_support' },
};

const FALLBACK: EditorMessage = { text: 'Something went wrong. Your edit is safe.', action: 'retry' };

/** Copy for an error code; unknown codes fall back to the server's message, then a generic line. */
export function editorMessage(code: string | undefined, serverMessage?: string): EditorMessage {
  return (code && MESSAGES[code]) || (serverMessage ? { text: serverMessage, action: 'retry' } : FALLBACK);
}

/** The rebase toast (02-editor §2.3). */
export const droppedEditMessage = (label?: string): string =>
  label ? `Your edit to ${label} was replaced by Clipnera's change.` : "One of your edits was replaced by Clipnera's change.";

/** The save-state line under the title (02-editor §2.1). */
export const SAVE_STATE_TEXT = {
  saved: 'Saved',
  saving: 'Saving',
  error: 'Not saved',
  offline: 'Offline · changes kept on this device',
} as const;
