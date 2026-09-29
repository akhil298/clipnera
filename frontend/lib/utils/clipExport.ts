import { clipApi } from '@/lib/api';
import type { VideoProject } from '@/lib/types';

/** Saves a signed export URL. The URLs are signed to download as attachments,
 * so a same-tab click saves the file; `target="_blank"` would only open a tab
 * showing the video. */
export function downloadFile(url: string, filename: string): void {
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/** Renders every clip in the project with captions and downloads them as one
 * ZIP. Separate files do not work: the URLs are on S3, so the browser ignores
 * `download`, each click navigates this tab, and back-to-back navigations
 * cancel each other. Uses the first clip's caption style, size and hook
 * transition for all of them (Auto still picks per clip). */
export async function exportAllProjectClips(
  project: Pick<VideoProject, 'clips'> & Partial<Pick<VideoProject, 'id' | 'title'>>,
): Promise<void> {
  if (!project.id || project.clips.length === 0) {
    throw new Error('There are no clips available to export.');
  }

  const firstClip = project.clips[0];
  const result = await clipApi.exportProject(project.id, {
    clipIds: project.clips.map((clip) => clip.id),
    aspectRatio: firstClip?.aspectRatio,
    captionConfig: firstClip?.captionConfig,
    hookTransition: firstClip?.hookTransition,
    bundle: true,
  });

  if (!result.bundle_presigned_url) {
    throw new Error('The export completed without producing a downloadable file.');
  }
  downloadFile(result.bundle_presigned_url, `${project.title || 'clips'}.zip`);
}
