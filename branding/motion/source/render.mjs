#!/usr/bin/env node
// Renders Clipnera's motion pieces to video with the local Chrome and FFmpeg.
// No npm packages: Chrome is driven over the DevTools protocol.
//
//   node branding/motion/source/render.mjs                 # production + library
//   node branding/motion/source/render.mjs production      # files the backend uses
//   node branding/motion/source/render.mjs library --only the-moment
//   node branding/motion/source/render.mjs motion --spec specs.json --out dir/
//
// `motion` renders template graphics (templates.js) from a list of specs, one transparent
// PNG-in-MOV per spec, sized to its slot box, plus a manifest.json of what it rendered:
//
//   [{"name": "users", "template": "count-up", "dur": 2.5, "W": 900, "H": 420,
//     "fields": {"value": 10000, "suffix": "+", "label": "users in a month"}, "accent": "#f59e0b"}]
//
// CHROME_PATH overrides the Chrome binary (defaults to the macOS app).
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../../..');
const LIBRARY = path.join(ROOT, 'branding/motion-library');
const STATIC = path.join(ROOT, 'backend/static/motion/branding');
const CHROME = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const catalog = JSON.parse(await readFile(path.join(HERE, 'catalog.json'), 'utf8'));
const FPS = catalog.fps;
const rel = p => path.relative(ROOT, p);

/* ---------- Chrome over the DevTools protocol ---------- */
function connect(url) {
  const ws = new WebSocket(url), pending = new Map();
  let next = 0;
  ws.onmessage = e => {
    const msg = JSON.parse(e.data), p = pending.get(msg.id);
    if (!p) return;
    pending.delete(msg.id);
    msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
  };
  return new Promise((resolve, reject) => {
    ws.onerror = () => reject(new Error(`Cannot reach DevTools at ${url}`));
    ws.onopen = () => resolve({
      send: (method, params = {}) => new Promise((res, rej) => {
        const id = ++next;
        pending.set(id, { resolve: res, reject: rej });
        ws.send(JSON.stringify({ id, method, params }));
      }),
      close: () => ws.close(),
    });
  });
}

async function launchChrome() {
  const profile = await mkdtemp(path.join(tmpdir(), 'clipnera-motion-'));
  const proc = spawn(CHROME, [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--no-default-browser-check', '--allow-file-access-from-files', '--hide-scrollbars', '--force-color-profile=srgb',
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((resolve, reject) => {
    let log = '';
    proc.stderr.on('data', d => {
      log += d;
      const found = log.match(/DevTools listening on (ws:\/\/\S+)/);
      if (found) resolve(found[1]);
    });
    proc.on('exit', code => reject(new Error(`Chrome exited (${code}) before DevTools was ready:\n${log}`)));
  });
  const targets = await (await fetch(`http://127.0.0.1:${new URL(wsUrl).port}/json/list`)).json();
  const cdp = await connect(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
  return {
    cdp,
    async close() {
      cdp.close();
      await new Promise(r => { proc.once('exit', r); proc.kill(); });
      await rm(profile, { recursive: true, force: true });
    },
  };
}

async function evaluate(cdp, expression) {
  const r = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
}

async function openPage(cdp, file) {
  await cdp.send('Page.navigate', { url: pathToFileURL(path.join(HERE, file)).href });
  for (let i = 0; i < 100; i++) {
    const state = await evaluate(cdp, 'window.harnessError || (window.harnessReady === true)');
    if (typeof state === 'string') throw new Error(`${file}: ${state}`);
    if (state) return;
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error(`${file} did not get ready`);
}

/* ---------- FFmpeg ---------- */
function encoder(out, { alpha }) {
  // PNG-in-MOV keeps transparency and decodes with any FFmpeg build.
  const codec = alpha
    ? ['-c:v', 'png', '-pix_fmt', 'rgba']
    : ['-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'];
  const proc = spawn('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-', ...codec, out,
  ], { stdio: ['pipe', 'ignore', 'pipe'] });
  let err = '';
  proc.stderr.on('data', d => { err += d; });
  const done = new Promise((res, rej) => proc.on('exit', code => (code === 0 ? res() : rej(new Error(`ffmpeg failed for ${out}: ${err}`)))));
  return {
    write: buf => new Promise(res => (proc.stdin.write(buf) ? res() : proc.stdin.once('drain', res))),
    end: () => { proc.stdin.end(); return done; },
  };
}
const fromDataUrl = url => Buffer.from(url.slice(url.indexOf(',') + 1), 'base64');

/* ---------- frame sources ---------- */
// Round 2 is canvas code (signature.html); round 1 is CSS animation (reel.html).
/** Encodes the data-URL frame ``call(t)`` returns for every time in ``times``. */
async function renderCanvas(cdp, out, times, call, alpha) {
  const enc = encoder(out, { alpha });
  for (const t of times) await enc.write(fromDataUrl(await evaluate(cdp, call(t))));
  await enc.end();
}

async function renderSignature(cdp, out, times, { id, W, H, layer = false, backdrop = null, alpha = false }) {
  // Only a .mov keeps the transparency; an .mp4 of transparent frames keeps
  // their colour, and the backend restores any fade with the manifest's fade_in_s.
  await renderCanvas(cdp, out, times,
    t => `Harness.frame(${JSON.stringify({ id, t, W, H, layer, backdrop, alpha })})`, alpha && out.endsWith('.mov'));
}

async function renderReel(cdp, out, times, { id }) {
  const [W, H] = catalog.library_size, cssW = 360;
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: cssW, height: cssW * H / W, deviceScaleFactor: W / cssW, mobile: false });
  await evaluate(cdp, `Reel.mount(${JSON.stringify(id)})`);
  const enc = encoder(out, { alpha: false });
  for (const t of times) {
    await evaluate(cdp, `Reel.seek(${t})`);
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 95, clip: { x: 0, y: 0, width: cssW, height: cssW * H / W, scale: 1 } });
    await enc.write(Buffer.from(data, 'base64'));
  }
  await enc.end();
  await cdp.send('Emulation.clearDeviceMetricsOverride');
}

/** Frame times for ``segments`` of the source loop played at ``speed``. */
function remapTimes(segments, speed) {
  const length = segments.reduce((sum, [a, b]) => sum + b - a, 0);
  const frames = Math.round(length / speed * FPS);
  return Array.from({ length: frames }, (_, n) => {
    let u = n / FPS * speed;
    for (const [a, b] of segments) {
      if (u <= b - a) return a + u;
      u -= b - a;
    }
    return segments.at(-1)[1];
  });
}

/* ---------- production: what the backend renders with ---------- */
async function production(cdp) {
  const { sizes, outro, watermark } = catalog.production;
  await openPage(cdp, 'signature.html');
  const manifest = { fps: FPS };
  // The end card is opaque but for its quarter-second fade-in, so it ships as a
  // small MP4 (PNG-in-MOV ran past GitHub's 100 MB file limit) and the backend
  // fades it in over the clip.
  for (const [key, spec, ext, opts] of [['outro', outro, 'mp4', { layer: true, alpha: true }]]) {
    const times = remapTimes(spec.segments, spec.speed), dir = path.join(STATIC, key), files = {};
    await mkdir(dir, { recursive: true });
    for (const [name, [W, H]] of Object.entries(sizes)) {
      const out = path.join(dir, `${spec.slug}_${name}.${ext}`);
      console.log(`production ${key} ${name} -> ${rel(out)}`);
      await renderSignature(cdp, out, times, { id: spec.id, W, H, ...opts });
      files[name] = path.relative(STATIC, out);
    }
    manifest[key] = {
      slug: spec.slug, duration: times.length / FPS, files,
      ...(spec.blur_in_s ? { blur_in_s: spec.blur_in_s } : {}), ...(spec.fade_in_s ? { fade_in_s: spec.fade_in_s } : {}),
    };
  }

  const dir = path.join(STATIC, 'watermark', watermark.slug);
  await mkdir(dir, { recursive: true });
  console.log(`production watermark sprites -> ${rel(dir)}`);
  const sprites = await evaluate(cdp, `Harness.sparkSprites(${watermark.levels})`);
  const save = async (name, shot) => { await writeFile(path.join(dir, name), fromDataUrl(shot.png)); return { file: name, x: shot.x, y: shot.y }; };
  const pad = i => String(i).padStart(2, '0');
  const layout = {
    ref: sprites.ref, levels: sprites.levels, bar_lag_s: sprites.bar_lag_s, box: sprites.box, anchor: sprites.anchor,
    word: await save('word.png', sprites.word),
    tiles: await Promise.all(sprites.tiles.map((s, i) => save(`tile_${pad(i)}.png`, s))),
    bars: await Promise.all(sprites.bars.map((s, i) => save(`bar_${pad(i)}.png`, s))),
    bar_x: sprites.bar_x,
  };
  await writeFile(path.join(dir, 'layout.json'), JSON.stringify(layout, null, 2) + '\n');
  manifest.watermark = { slug: watermark.slug, layout: path.relative(STATIC, path.join(dir, 'layout.json')) };
  await writeFile(path.join(STATIC, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
}

/* ---------- library: every motion, with its details ---------- */
function motionReadme(m) {
  const type = catalog.types[m.type];
  const source = m.page === 'signature'
    ? `\`branding/motion/source/kit.js\`, function \`${m.id}\``
    : `\`branding/motion/source/reel.html\`, piece \`${m.id}\``;
  const live = Object.entries(catalog.production).find(([, spec]) => spec.slug === m.slug);
  const lines = [
    `# ${m.name}`, '',
    '| | |', '|---|---|',
    `| Type | ${type.label} |`,
    `| Status | ${m.status} |`,
    `| Preview | \`${m.slug}.mp4\`, ${catalog.library_size.join('×')}, ${FPS} fps, ${m.render_s} s |`,
    `| Design round | ${m.round} |`,
    `| Source | ${source} |`, '',
    '## What happens', '', m.what, '',
    '## Why it fits Clipnera', '', m.why, '',
  ];
  if (m.beats) lines.push('## Beats', '', ...m.beats.map(([at, beat]) => `- **${at}** ${beat}`), '');
  if (live) {
    const [key] = live;
    lines.push('## Where it runs', '',
      key === 'watermark'
        ? 'Sprites in `backend/static/motion/branding/watermark/listening-spark/`. `backend/branding/watermark.py` rebuilds every frame from the clip\'s loudness and `backend/branding/service.py` lays it over the top-right corner.'
        : `Rendered for 9:16, 16:9 and 1:1 in \`backend/static/motion/branding/${key}/\`. \`backend/branding/service.py\` adds it to every branded export.`,
      '');
  }
  lines.push('## Re-render', '', '```sh', `node branding/motion/source/render.mjs library --only ${m.slug}`, '```', '');
  return lines.join('\n');
}

function libraryReadme() {
  const lines = [
    '# Clipnera motion library', '',
    'Every Clipnera brand motion, one folder each, with a preview video and its details.',
    'Generated by `branding/motion/source/render.mjs` from `catalog.json`; edit the catalog, not these files.', '',
  ];
  for (const [key, type] of Object.entries(catalog.types)) {
    lines.push(`## ${type.label}s`, '', '| Motion | Status | What it does |', '|---|---|---|');
    for (const m of catalog.motions.filter(x => x.type === key)) {
      lines.push(`| [${m.name}](${type.dir}/${m.slug}/README.md) | ${m.status} | ${m.what.split('. ')[0].replace(/\.$/, '')}. |`);
    }
    lines.push('');
  }
  return lines.join('\n');
}

async function library(cdp, only) {
  const motions = catalog.motions.filter(m => !only || m.slug === only);
  if (!motions.length) throw new Error(`No motion called "${only}" in catalog.json`);
  let page = null;
  for (const m of motions) {
    const dir = path.join(LIBRARY, catalog.types[m.type].dir, m.slug), out = path.join(dir, `${m.slug}.mp4`);
    await mkdir(dir, { recursive: true });
    const file = m.page === 'signature' ? 'signature.html' : 'reel.html';
    if (page !== file) { await openPage(cdp, file); page = file; }
    const times = Array.from({ length: Math.round(m.render_s * FPS) }, (_, n) => n / FPS);
    console.log(`library ${m.slug} -> ${rel(out)}`);
    if (m.page === 'signature') {
      const [W, H] = catalog.library_size;
      await renderSignature(cdp, out, times, { id: m.id, W, H, backdrop: m.backdrop ?? null, layer: m.layer ?? false });
    } else {
      await renderReel(cdp, out, times, { id: m.id });
    }
    await writeFile(path.join(dir, 'README.md'), motionReadme(m));
  }
  await writeFile(path.join(LIBRARY, 'README.md'), libraryReadme());
}

/* ---------- motion: template graphics placed by the director ---------- */
async function motion(cdp, specFile, outDir) {
  const specs = JSON.parse(await readFile(specFile, 'utf8'));
  await openPage(cdp, 'motion.html');
  // Every spec is checked before the first frame, so a bad one fails the batch cheaply.
  for (const spec of specs) await evaluate(cdp, `Motion.check(${JSON.stringify(spec)})`);
  await mkdir(outDir, { recursive: true });
  const rendered = [];
  for (const spec of specs) {
    const out = path.join(outDir, `${spec.name}.mov`), started = performance.now();
    const times = Array.from({ length: Math.round(spec.dur * FPS) }, (_, n) => n / FPS);
    await renderCanvas(cdp, out, times, t => `Motion.frame(${JSON.stringify({ ...spec, t })})`, true);
    const seconds = (performance.now() - started) / 1000;
    console.log(`motion ${spec.name} (${spec.template}) ${times.length} frames in ${seconds.toFixed(2)} s -> ${out}`);
    rendered.push({ name: spec.name, template: spec.template, file: path.basename(out), W: spec.W, H: spec.H,
      dur: spec.dur, frames: times.length, render_s: Number(seconds.toFixed(3)) });
  }
  await writeFile(path.join(outDir, 'manifest.json'), JSON.stringify({ fps: FPS, motions: rendered }, null, 2) + '\n');
}

/* ---------- main ---------- */
const args = process.argv.slice(2);
const FLAGS = ['--only', '--spec', '--out'];
const flag = name => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : null; };
const flagValues = new Set(FLAGS.map(f => args.indexOf(f)).filter(i => i >= 0).map(i => i + 1));
const only = flag('--only');
const jobs = args.filter((a, i) => !a.startsWith('--') && !flagValues.has(i));
const run = jobs.length ? jobs : ['production', 'library'];
if (run.includes('motion') && !(flag('--spec') && flag('--out'))) throw new Error('motion needs --spec <file> and --out <dir>');
const chrome = await launchChrome();
try {
  if (run.includes('production')) await production(chrome.cdp);
  if (run.includes('library')) await library(chrome.cdp, only);
  if (run.includes('motion')) await motion(chrome.cdp, path.resolve(flag('--spec')), path.resolve(flag('--out')));
} finally {
  await chrome.close();
}
