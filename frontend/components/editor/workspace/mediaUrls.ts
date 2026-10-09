import type { UrlResolver } from '@/lib/media';

/**
 * The PreviewEngine's URL source for editor projects.
 * NEEDS-BACKEND: signed editor asset URLs, e.g. `GET /editor/projects/{id}/assets` →
 * `{asset_id: {url, proxy_url, expires_at}}` with a `refresh` flag (05-playback-api.md). There is no
 * such route yet, so every source is refused and the engine reports `media-error`, which the preview
 * zone shows as "This video could not play. Your edit is safe."
 */
export const resolveEditorMedia: UrlResolver = async (ref) => {
  throw new Error(`No playable link for ${ref.kind === 'asset' ? `asset ${ref.asset.id}` : ref.kind} yet.`);
};
