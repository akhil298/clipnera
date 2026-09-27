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

/** Renders every clip in the project with captions and downloads each one.
 * Uses the first clip's caption style, size and hook transition for all of
 * them (Auto still picks per clip). */
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
  });

  const downloadable = result.exported_clips.filter((clip) => clip.burned_presigned_url);
  if (downloadable.length === 0) {
    throw new Error('The export completed without producing downloadable files.');
  }
  downloadable.forEach((clip, index) => {
    downloadFile(
      clip.burned_presigned_url as string,
      `${project.title || 'clip'}-${clip.clip_id}-${clip.platform}-${index + 1}.mp4`,
    );
  });
}
