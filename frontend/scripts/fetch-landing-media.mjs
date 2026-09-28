// Downloads the landing page videos listed in lib/landingMedia.json from Pexels
// into public/media/landing/<key>.mp4. Needs a free Pexels API key in
// PEXELS_API_KEY (https://www.pexels.com/api/). Existing files are kept.
//
//   PEXELS_API_KEY=... npm run media:landing

import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const outDir = path.join(root, 'public', 'media', 'landing');
const TARGET_WIDTH = 960;

const apiKey = process.env.PEXELS_API_KEY;
if (!apiKey) {
  console.error('Set PEXELS_API_KEY to download the landing videos.');
  process.exit(1);
}

const sources = JSON.parse(await readFile(path.join(root, 'lib', 'landingMedia.json'), 'utf8'));
await mkdir(outDir, { recursive: true });

const exists = (file) => access(file).then(() => true, () => false);

/** The smallest MP4 at least TARGET_WIDTH wide, else the widest one available. */
function pickFile(files) {
  const mp4s = files.filter((f) => f.file_type === 'video/mp4' && f.width).sort((a, b) => a.width - b.width);
  return mp4s.find((f) => Math.min(f.width, f.height) >= TARGET_WIDTH * 0.5625) ?? mp4s.at(-1);
}

for (const [key, { pexelsId }] of Object.entries(sources)) {
  const target = path.join(outDir, `${key}.mp4`);
  if (await exists(target)) {
    console.log(`${key}: already downloaded`);
    continue;
  }
  const res = await fetch(`https://api.pexels.com/videos/videos/${pexelsId}`, { headers: { Authorization: apiKey } });
  if (!res.ok) throw new Error(`${key}: Pexels API returned ${res.status}`);
  const file = pickFile((await res.json()).video_files ?? []);
  if (!file) throw new Error(`${key}: no MP4 file listed`);
  const video = await fetch(file.link);
  if (!video.ok) throw new Error(`${key}: download returned ${video.status}`);
  await writeFile(target, Buffer.from(await video.arrayBuffer()));
  console.log(`${key}: ${file.width}x${file.height} saved`);
}
