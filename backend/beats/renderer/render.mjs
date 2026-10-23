#!/usr/bin/env node
// Renders a clip's graphic beats to transparent videos with headless Chrome and FFmpeg.
// No npm packages: Chrome is driven over the DevTools protocol (Node 22+ has fetch and WebSocket).
//
//   node render.mjs <spec.json> <out-dir>
//
// spec.json: {"W":1080,"H":1920,"fps":30,"beats":[{"id":"b0","kind":"count_up","dur":2.2,...}]}
// Each beat becomes <out-dir>/<id>.mov (PNG-in-MOV, full frame, alpha) and the run writes
// <out-dir>/rendered.json listing what was made. CHROME_PATH names the browser binary.
import { spawn } from 'node:child_process';
import { access, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CANDIDATES = [
  process.env.CHROME_PATH,
  '/opt/chrome-headless-shell/chrome-headless-shell',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome',
].filter(Boolean);

async function chromePath() {
  for (const candidate of CANDIDATES) {
    try { await access(candidate); return candidate; } catch { /* next */ }
  }
  throw new Error(`No Chrome found; set CHROME_PATH (tried ${CANDIDATES.join(', ')})`);
}

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
  const profile = await mkdtemp(path.join(tmpdir(), 'clipnera-beats-'));
  const proc = spawn(await chromePath(), [
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
    '--no-default-browser-check', '--allow-file-access-from-files', '--hide-scrollbars', '--force-color-profile=srgb',
    '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', 'about:blank',
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
      if (proc.exitCode === null && proc.signalCode === null) {
        await new Promise(r => {
          const force = setTimeout(() => { proc.kill('SIGKILL'); r(); }, 3000);
          proc.once('exit', () => { clearTimeout(force); r(); });
          proc.kill();
        });
      }
      await rm(profile, { recursive: true, force: true });
    },
  };
}

async function evaluate(cdp, expression) {
  const r = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
}

function encoder(out, fps) {
  // PNG-in-MOV keeps the alpha channel and decodes with any FFmpeg build.
  const proc = spawn('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    '-c:v', 'png', '-pix_fmt', 'rgba', out,
  ], { stdio: ['pipe', 'ignore', 'pipe'] });
  let err = '';
  proc.stderr.on('data', d => { err += d; });
  const done = new Promise((res, rej) => proc.on('exit', code => (code === 0 ? res() : rej(new Error(`ffmpeg failed for ${out}: ${err}`)))));
  return {
    write: buf => new Promise(res => (proc.stdin.write(buf) ? res() : proc.stdin.once('drain', res))),
    end: () => { proc.stdin.end(); return done; },
  };
}

async function renderBeat(cdp, beat, { W, H, fps }, out) {
  await evaluate(cdp, `Beats.mount(${JSON.stringify({ ...beat, W, H })})`);
  const frames = Math.max(1, Math.round(beat.dur * fps));
  const enc = encoder(out, fps);
  for (let n = 0; n < frames; n++) {
    await evaluate(cdp, `Beats.seek(${n / fps})`);
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: W, height: H, scale: 1 } });
    await enc.write(Buffer.from(data, 'base64'));
  }
  await enc.end();
  return frames;
}

// A beat gets this long to render (plus its own length); a hung page is replaced and the next beat goes on.
const BEAT_TIMEOUT_MS = 30000;

async function openPage(W, H) {
  const chrome = await launchChrome();
  const { cdp } = chrome;
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  await cdp.send('Page.navigate', { url: pathToFileURL(path.join(HERE, 'page.html')).href });
  for (let i = 0; i < 100 && !(await evaluate(cdp, 'window.Beats?.ready === true')); i++) await new Promise(r => setTimeout(r, 100));
  await evaluate(cdp, 'document.fonts.ready.then(() => true)');
  return chrome;
}

function withTimeout(promise, ms, what) {
  let timer;
  const timeout = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(`${what} timed out after ${ms} ms`)), ms); });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

async function main() {
  const [specPath, outDir] = process.argv.slice(2);
  if (!specPath || !outDir) throw new Error('usage: node render.mjs <spec.json> <out-dir>');
  const spec = JSON.parse(await readFile(specPath, 'utf8'));
  const { W, H } = spec, fps = spec.fps || 30;
  let chrome = await openPage(W, H);
  const rendered = [];
  try {
    for (const beat of spec.beats) {
      const out = path.join(outDir, `${beat.id}.mov`);
      try {
        const frames = await withTimeout(renderBeat(chrome.cdp, beat, { W, H, fps }, out), BEAT_TIMEOUT_MS + beat.dur * 4000, `beat ${beat.id}`);
        rendered.push({ id: beat.id, file: out, frames });
      } catch (err) {
        // One broken beat is left out; a page that stopped answering is replaced so the rest still render.
        rendered.push({ id: beat.id, error: String(err.message || err) });
        await chrome.close().catch(() => undefined);
        chrome = await openPage(W, H);
      }
    }
  } finally {
    await chrome.close().catch(() => undefined);
  }
  await writeFile(path.join(outDir, 'rendered.json'), JSON.stringify(rendered, null, 2));
}

main().catch(err => { console.error(err.stack || String(err)); process.exit(1); });
