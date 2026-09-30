/* Clipnera motion kit: every round-2 piece drawn as a pure function of time.
 * Loaded by signature.html; render.mjs turns these frames into video files.
 * Copied from the review page (claude.ai/artifact/BfNH3sUN3n2WaWDRjzm5de); edit here now. */
/* ---------- shared drawing kit ---------- */
const AMBER = '#f59e0b', INK = '#0a0a0a', BG = '#0b0a09';
const STAR = new Path2D('M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z');
const CROSS = new Path2D('M20 3v4M22 5h-4M4 17v2M5 18H3');
const STAR_LEN = 66;
let DPR = 1;

const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const seg = (t, a, b) => cl((t - a) / (b - a));
const lerp = (a, b, k) => a + (b - a) * k;
const eo3 = x => 1 - Math.pow(1 - x, 3);
const eio = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
const eback = x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const bump = x => Math.sin(Math.PI * cl(x));
const pad2 = n => String(n).padStart(2, '0');
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

function tile(ctx, cx, cy, s, o = {}) {
  const { alpha = 1, rot = 0, sx = 1, star = 1, starScale = 1, starRot = 0, cross = 1, fill = AMBER, stroke = INK, fillA = 1 } = o;
  if (alpha <= 0 || s <= 0) return;
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.translate(cx, cy); ctx.rotate(rot); ctx.scale(s / 32 * sx, s / 32); ctx.translate(-16, -16);
  if (fillA > 0) { ctx.save(); ctx.globalAlpha *= fillA; ctx.fillStyle = fill; ctx.beginPath(); ctx.roundRect(0, 0, 32, 32, 9); ctx.fill(); ctx.restore(); }
  if (star > 0) {
    ctx.shadowColor = 'transparent';
    ctx.translate(6, 6); ctx.scale(.8333, .8333);
    ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.save(); ctx.translate(12, 12); ctx.rotate(starRot); ctx.scale(starScale, starScale); ctx.translate(-12, -12);
    if (star < 1) ctx.setLineDash([STAR_LEN * star, STAR_LEN]);
    ctx.stroke(STAR); ctx.restore();
    if (cross > 0) { ctx.globalAlpha *= cross; ctx.stroke(CROSS); }
  }
  ctx.restore();
}
function letters(ctx, fs) {
  ctx.font = `800 ${fs}px Syne, sans-serif`;
  const tr = -0.02 * fs; let x = 0;
  return [...'clipnera'].map((ch, i) => { const w = ctx.measureText(ch).width; const o = { ch, i, x, w, nera: i >= 4 }; x += w + tr; return o; });
}
const wordWidth = ls => ls[7].x + ls[7].w;
function lockup(ctx, fs) { const ww = wordWidth(letters(ctx, fs)), ts = 1.3 * fs, gap = .36 * fs; return { ts, gap, ww, total: ts + gap + ww }; }
function drawWord(ctx, x, y, fs, o = {}) {
  const { alpha = 1, reveal = 1, fx = null, clipC = '#fff', neraC = AMBER } = o;
  const ls = letters(ctx, fs);
  if (alpha <= 0 || reveal <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
  if (reveal < 1) { ctx.beginPath(); ctx.rect(x - fs, y - fs * 2, fs + wordWidth(ls) * reveal, fs * 4); ctx.clip(); }
  for (const l of ls) {
    const f = fx ? fx(l) : {}; const a = f.a ?? 1; if (a <= 0) continue;
    ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = f.color ?? (l.nera ? neraC : clipC);
    ctx.translate(x + l.x + l.w / 2 + (f.dx || 0), y + (f.dy || 0) + fs * .04);
    if (f.s !== undefined) ctx.scale(f.s, f.s);
    if (f.r) ctx.rotate(f.r);
    ctx.fillText(l.ch, 0, 0); ctx.restore();
  }
  ctx.restore();
}
function text(ctx, s, x, y, size, color, alpha = 1, weight = 600, family = 'Plus Jakarta Sans', align = 'center') {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha;
  ctx.font = `${weight} ${size}px ${family === 'mono' ? '"JetBrains Mono", monospace' : family + ', sans-serif'}`;
  ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = 'middle';
  ctx.fillText(s, x, y); ctx.restore();
}
function bg(ctx, W, H) {
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  const r = Math.max(W, H) * .65, g = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, r);
  g.addColorStop(0, 'rgba(245,158,11,.07)'); g.addColorStop(1, 'rgba(245,158,11,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}
function blob(ctx, x, y, r, h, s, l, a) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, `hsla(${h},${s}%,${l}%,${a})`); g.addColorStop(1, `hsla(${h},${s}%,${l}%,0)`);
  ctx.fillStyle = g; ctx.fillRect(x - r, y - r, 2 * r, 2 * r);
}
const headX = (x, w, t) => x + w * (.58 + .015 * Math.sin(t * 1.3));
function scene(ctx, x, y, w, h, hue, t) {
  ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
  const g = ctx.createLinearGradient(x, y, x + w * .4, y + h);
  g.addColorStop(0, `hsl(${hue} 32% 20%)`); g.addColorStop(1, `hsl(${hue + 30} 36% 7%)`);
  ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
  const M = Math.max(w, h);
  blob(ctx, x + w * (.25 + .04 * Math.sin(t * .4)), y + h * .3, M * .45, hue, 75, 58, .45);
  blob(ctx, x + w * .8, y + h * (.65 + .03 * Math.sin(t * .5)), M * .5, hue + 40, 65, 48, .45);
  const sx = headX(x, w, t), base = y + h, sh = h * .72;
  ctx.fillStyle = `hsl(${hue} 20% 9%)`;
  ctx.beginPath(); ctx.ellipse(sx, base, sh * .42, sh * .36, 0, Math.PI, 0); ctx.fill();
  ctx.beginPath(); ctx.arc(sx, base - sh * .52, sh * .17, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
  return { hx: sx, hy: base - sh * .52, hr: sh * .17 };
}
function ring(ctx, x, y, r, lw, alpha) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = AMBER; ctx.lineWidth = lw;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
}
function pill(ctx, x, y, w, h, fill, stroke) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, h / 2);
  ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = Math.max(1, h * .04); ctx.stroke(); }
}

/* ---------- F1 The Moment ---------- */
function F1(ctx, W, H, t) {
  bg(ctx, W, H);
  const m = Math.min(W, H), u = m / 100, fs = m * .1, cx = W / 2, cy = H / 2, lk = lockup(ctx, fs), ts = lk.ts;
  ctx.globalAlpha = 1 - seg(t, 6.5, 7.1);
  const N = 72, x0 = W * .08, x1 = W * .92, step = (x1 - x0) / N, bw = Math.max(1, step * .52), A = Math.min(H * .17, W * .13);
  const pk = 46, s0 = pk - 5, s1 = pk + 5;
  const pkX = x0 + step * pk + bw / 2;
  const scanX = t < 2.3 ? lerp(x0, x1, eio(seg(t, 1.0, 2.3))) : lerp(x1, pkX, eio(seg(t, 2.3, 2.8)));
  const reached = t < 2.3 ? scanX : x1;
  const scanOn = seg(t, .9, 1.05) * (1 - seg(t, 2.9, 3.1));
  const selP = eo3(seg(t, 2.75, 3.05));
  const selX0 = x0 + step * s0, selX1 = x0 + step * s1 + bw, selW = selX1 - selX0, selCx = (selX0 + selX1) / 2;
  const morph = eio(seg(t, 3.2, 4.1)), fillA = seg(t, 3.5, 4.0), barFade = 1 - seg(t, 3.8, 4.15);
  const rw = lerp(selW, ts, morph), rh = lerp(2 * A, ts, morph), rcx = lerp(selCx, cx, morph), rad = lerp(bw / 2, ts * 9 / 32, morph);

  const tcA = seg(t, .3, .9) * (1 - seg(t, 2.9, 3.3));
  text(ctx, '00:00:00', x0, cy + A * 1.4 + fs * .2, fs * .24, 'rgba(255,255,255,.5)', tcA, 500, 'mono', 'left');
  text(ctx, '01:24:37', x1, cy + A * 1.4 + fs * .2, fs * .24, 'rgba(255,255,255,.5)', tcA, 500, 'mono', 'right');

  const bars = [];
  for (let i = 0; i < N; i++) {
    const x = x0 + step * i, sel = i >= s0 && i <= s1;
    const amp = sel ? .78 + .22 * Math.abs(Math.sin(i * 1.7)) : .14 + .72 * Math.abs(Math.sin(i * .61) * Math.cos(i * .23 + .8));
    const grow = eo3(seg(t, .1 + i * .008, .7 + i * .008));
    const d = (x + bw / 2 - scanX) / step, near = scanOn * Math.exp(-d * d / 5);
    const h = amp * A * grow * (1 + .3 * near);
    const base = .16 + (x < reached ? .14 : 0) + .6 * near;
    if (sel) { bars.push({ x, h, base }); continue; }
    const k = Math.abs(i - pk) * .006, v = 1 - eio(seg(t, 3.0 + k, 3.4 + k));
    if (v <= 0 || h <= 0) continue;
    ctx.fillStyle = `rgba(255,255,255,${base * v})`;
    ctx.beginPath(); ctx.roundRect(x, cy - h * v, bw, 2 * h * v, bw / 2); ctx.fill();
  }
  if (scanOn > 0) {
    ctx.save(); ctx.globalAlpha *= scanOn;
    const g = ctx.createLinearGradient(scanX - step * 5, 0, scanX + step * 5, 0);
    g.addColorStop(0, 'rgba(245,158,11,0)'); g.addColorStop(.5, 'rgba(245,158,11,.3)'); g.addColorStop(1, 'rgba(245,158,11,0)');
    ctx.fillStyle = g; ctx.fillRect(scanX - step * 5, cy - A * 1.3, step * 10, A * 2.6);
    ctx.fillStyle = AMBER; const lw = Math.max(2, u * .35);
    ctx.fillRect(scanX - lw / 2, cy - A * 1.3, lw, A * 2.6);
    ctx.translate(scanX, cy - A * 1.3 - u * 2.2); const k = u * 3.4 / 24; ctx.scale(k, k); ctx.translate(-12, -12); ctx.fill(STAR);
    ctx.restore();
  }
  if (fillA > 0 && t < 4.1) {
    ctx.save(); ctx.globalAlpha *= fillA; ctx.fillStyle = AMBER;
    ctx.beginPath(); ctx.roundRect(rcx - rw / 2, cy - rh / 2, rw, rh, rad); ctx.fill(); ctx.restore();
  }
  if (barFade > 0) for (const b of bars) {
    const bx = rcx - rw / 2 + (b.x - selX0) / selW * rw, bwi = bw * rw / selW, bh = b.h * rh / (2 * A);
    ctx.save(); ctx.globalAlpha *= barFade;
    const draw = (c, a) => { if (a <= 0) return; ctx.fillStyle = c; ctx.globalAlpha = a * barFade * (1 - seg(t, 6.5, 7.1)); ctx.beginPath(); ctx.roundRect(bx, cy - bh, bwi, 2 * bh, bwi / 2); ctx.fill(); };
    draw(`rgba(255,255,255,${b.base})`, 1 - selP);
    draw(AMBER, selP * (1 - fillA));
    draw(INK, fillA * .85);
    ctx.restore();
  }
  const bA = seg(t, 2.75, 2.9) * (1 - seg(t, 3.2, 3.45));
  if (bA > 0) {
    const bp = eback(seg(t, 2.75, 3.1)), padX = step * (.8 + 2.4 * (1 - bp)), bh = A * 1.15, arm = step * 1.3;
    ctx.save(); ctx.globalAlpha *= bA; ctx.strokeStyle = AMBER; ctx.lineWidth = Math.max(1.5, u * .45); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    const L = selX0 - padX, R = selX1 + padX;
    ctx.beginPath();
    ctx.moveTo(L + arm, cy - bh); ctx.lineTo(L, cy - bh); ctx.lineTo(L, cy + bh); ctx.lineTo(L + arm, cy + bh);
    ctx.moveTo(R - arm, cy - bh); ctx.lineTo(R, cy - bh); ctx.lineTo(R, cy + bh); ctx.lineTo(R - arm, cy + bh);
    ctx.stroke(); ctx.restore();
    text(ctx, 'BEST MOMENT · 0:29', selCx, cy - bh - fs * .38, fs * .24, AMBER, bA, 500, 'mono');
  }
  if (t >= 4.1) {
    const slide = eio(seg(t, 4.55, 5.3)), tx = lerp(cx, cx - lk.total / 2 + ts / 2, slide);
    const rp = seg(t, 4.1, 4.9); if (rp < 1) ring(ctx, cx, cy, ts * (.6 + 1.8 * eo3(rp)), Math.max(1, u * .6 * (1 - rp)), (1 - rp) * .8);
    const rv = eo3(seg(t, 4.6, 5.4));
    drawWord(ctx, tx + ts / 2 + lk.gap - fs * .6 * (1 - rv), cy, fs, { reveal: rv });
    tile(ctx, tx, cy, ts, { star: seg(t, 4.1, 4.6), cross: seg(t, 4.55, 4.7) });
    const ta = eo3(seg(t, 5.3, 5.9));
    text(ctx, 'Every long video has a moment.', cx, cy + fs * 1.5 + fs * .3 * (1 - ta), fs * .34, '#b8ada0', ta);
  }
  ctx.globalAlpha = 1;
}

/* ---------- F2 Reframe ---------- */
function F2(ctx, W, H, t) {
  bg(ctx, W, H);
  const m = Math.min(W, H), u = m / 100, fs = m * .1, cx = W / 2, cy = H / 2, lk = lockup(ctx, fs), ts = lk.ts;
  const out = 1 - seg(t, 6.4, 7); ctx.globalAlpha = out;
  let fw = W * .86, fh = fw * 9 / 16; if (fh > H * .7) { fh = H * .7; fw = fh * 16 / 9; }
  const fx = cx - fw / 2, fy = cy - fh / 2;
  const inA = eo3(seg(t, 0, .7)), sc = .94 + .06 * inA;
  const ch = fh * .94, cw = ch * 9 / 16;
  const hx = headX(fx, fw, t);
  const follow = eio(seg(t, 1.5, 2.2)), cropCx = cl(lerp(cx, hx, follow), fx + cw / 2, fx + fw - cw / 2);
  const morph = eio(seg(t, 2.9, 3.8)), dim = seg(t, 1.4, 1.9), outside = 1 - seg(t, 2.6, 3.1);
  const r = { x: lerp(cropCx, cx, morph), w: lerp(cw, ts, morph), h: lerp(ch, ts, morph), rad: lerp(u * .6, ts * 9 / 32, morph) };
  const fillA = seg(t, 3.2, 3.75);

  if (t < 3.8) {
    ctx.save(); ctx.translate(cx, cy); ctx.scale(sc, sc); ctx.translate(-cx, -cy);
    if (outside > 0) {
      ctx.save(); ctx.globalAlpha *= inA * outside;
      ctx.beginPath(); ctx.roundRect(fx, fy, fw, fh, u * .8); ctx.clip();
      const hd = scene(ctx, fx, fy, fw, fh, 205, t);
      if (dim > 0) {
        ctx.fillStyle = `rgba(0,0,0,${.62 * dim})`; ctx.beginPath(); ctx.rect(fx, fy, fw, fh);
        ctx.roundRect(r.x - r.w / 2, cy - r.h / 2, r.w, r.h, r.rad); ctx.fill('evenodd');
      }
      ctx.restore();
      const ta = seg(t, .7, .9) * (1 - seg(t, 2.3, 2.6));
      if (ta > 0) {
        const bs = hd.hr * 1.5 * (1 + .6 * (1 - eo3(seg(t, .7, 1.1)))), jx = Math.sin(t * 7) * u * .15, arm = bs * .35;
        const L = hd.hx - bs + jx, R = hd.hx + bs + jx, T = hd.hy - bs, B = hd.hy + bs;
        ctx.save(); ctx.globalAlpha *= ta * inA; ctx.strokeStyle = '#fff'; ctx.lineWidth = Math.max(1.2, u * .35); ctx.lineCap = 'round';
        ctx.beginPath();
        for (const [px, py, dx, dy] of [[L, T, 1, 1], [R, T, -1, 1], [L, B, 1, -1], [R, B, -1, -1]]) { ctx.moveTo(px + dx * arm, py); ctx.lineTo(px, py); ctx.lineTo(px, py + dy * arm); }
        ctx.stroke(); ctx.restore();
        text(ctx, 'SPEAKER 1', L, T - fs * .25, fs * .2, '#fff', ta * inA, 500, 'mono', 'left');
      }
    }
    if (dim > 0) {
      ctx.save(); ctx.beginPath(); ctx.roundRect(r.x - r.w / 2, cy - r.h / 2, r.w, r.h, r.rad); ctx.clip();
      ctx.translate(r.x, cy); ctx.scale(r.h / ch, r.h / ch); ctx.translate(-cropCx, -cy);
      scene(ctx, fx, fy, fw, fh, 205, t); ctx.restore();
      if (fillA > 0) { ctx.save(); ctx.globalAlpha *= fillA; ctx.fillStyle = AMBER; ctx.beginPath(); ctx.roundRect(r.x - r.w / 2, cy - r.h / 2, r.w, r.h, r.rad); ctx.fill(); ctx.restore(); }
      const ba = dim * (1 - seg(t, 3.4, 3.7));
      if (ba > 0) {
        ctx.save(); ctx.globalAlpha *= ba; ctx.strokeStyle = AMBER; ctx.lineWidth = Math.max(1.5, u * .45);
        ctx.beginPath(); ctx.roundRect(r.x - r.w / 2, cy - r.h / 2, r.w, r.h, r.rad); ctx.stroke(); ctx.restore();
        text(ctx, '9:16', r.x, cy - r.h / 2 - fs * .3, fs * .22, AMBER, ba * (1 - morph), 500, 'mono');
      }
    }
    ctx.restore();
  } else {
    const slide = eio(seg(t, 4.0, 4.6)), tx = lerp(cx, cx - lk.total / 2 + ts / 2, slide), wx = tx + ts / 2 + lk.gap;
    const ls = letters(ctx, fs), clipEnd = ls[3].x + ls[3].w, neraX = ls[4].x, ww = wordWidth(ls);
    const p = eio(seg(t, 4.55, 4.8)), pa = seg(t, 4.2, 4.3) * (1 - seg(t, 5.0, 5.3));
    if (pa > 0) {
      const px0 = wx + lerp(0, neraX, p) - fs * .14, pw = lerp(clipEnd, ww - neraX, p) + fs * .28;
      ctx.save(); ctx.globalAlpha *= pa; pill(ctx, px0, cy - fs * .6, pw, fs * 1.2, AMBER); ctx.restore();
    }
    drawWord(ctx, wx, cy, fs, {
      fx: l => {
        const st = l.nera ? 4.55 : 4.2, e = seg(t, st, st + .28);
        const lit = pa > .5 && (l.nera ? p > .5 : p < .5);
        return { a: seg(t, st, st + .06), s: lerp(1.35, 1, eback(e)), color: lit ? INK : undefined };
      }
    });
    const rp = seg(t, 3.8, 4.5); if (rp < 1) ring(ctx, tx, cy, ts * (.6 + 1.4 * eo3(rp)), Math.max(1, u * .5), (1 - rp) * .7);
    const sp = eback(seg(t, 3.75, 4.2));
    tile(ctx, tx, cy, ts, { starScale: sp, starRot: (1 - sp) * -1.6, cross: seg(t, 4.1, 4.3) });
    const ta = eo3(seg(t, 5.1, 5.6));
    text(ctx, 'Landscape in. Shorts out.', cx, cy + fs * 1.5 + fs * .3 * (1 - ta), fs * .34, '#b8ada0', ta);
  }
  ctx.globalAlpha = 1;
}

/* ---------- F3 Thousand Frames ---------- */
let STAR_PTS = null;
function starPoints(n) {
  if (STAR_PTS) return STAR_PTS;
  const c = document.createElement('canvas').getContext('2d'), pts = [];
  for (let y = 0; y < 24; y += .42) for (let x = 0; x < 24; x += .42) if (c.isPointInPath(STAR, x, y)) pts.push({ x: (x - 12) / 24, y: (y - 12) / 24 });
  const r = rng(7);
  for (let i = pts.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [pts[i], pts[j]] = [pts[j], pts[i]]; }
  while (pts.length < n) pts.push({ ...pts[pts.length % 50], x: pts[pts.length % 50].x + (r() - .5) * .02 });
  return (STAR_PTS = pts.slice(0, n));
}
let PARTS = null;
function particles() {
  if (PARTS) return PARTS;
  const r = rng(42), hues = [38, 200, 330, 160, 265, 20], pts = starPoints(360);
  return (PARTS = pts.map(pt => {
    const rr = .12 + .88 * Math.sqrt(r());
    return { pt, rr, a: r() * Math.PI * 2, w: .25 + .45 / (rr + .3), hue: hues[Math.floor(r() * hues.length)], s: .6 + .8 * r(), rot0: r() * Math.PI, d: rr * .45 + r() * .2, o: r() };
  }));
}
function F3(ctx, W, H, t) {
  bg(ctx, W, H);
  const m = Math.min(W, H), u = m / 100, fs = m * .1, cx = W / 2, cy = H / 2, lk = lockup(ctx, fs), ts = lk.ts;
  ctx.globalAlpha = 1 - seg(t, 6.9, 7.5);
  const R = Math.max(W, H) * .62, S = m * .7;
  const col = eio(seg(t, 3.3, 3.72)), burst = seg(t, 3.72, 5.0), am = seg(t, 2.9, 3.3), fadeIn = seg(t, 0, .6);
  for (const p of particles()) {
    const ang = p.a + t * p.w * .55;
    const k = eio(seg(t, 1.2 + p.d, 2.6 + p.d));
    let x = lerp(cx + Math.cos(ang) * p.rr * R, cx + p.pt.x * S, k);
    let y = lerp(cy + Math.sin(ang) * p.rr * R * .62, cy + p.pt.y * S, k);
    const tx = cx + p.pt.x * ts * .7, ty = cy + p.pt.y * ts * .7;
    x = lerp(x, tx, col); y = lerp(y, ty, col);
    let size = u * 2.1 * p.s * (1 - .45 * k) * (1 - .6 * col), alpha = .85 * fadeIn, rot = (p.rot0 + t * .6) * (1 - k);
    const shimmer = bump(seg(t, 2.75 + (p.pt.x + .5) * .35, 3.05 + (p.pt.x + .5) * .35));
    let light = lerp(58, 55, am) + 22 * shimmer;
    if (burst > 0) {
      const b = eo3(burst), len = Math.hypot(p.pt.x, p.pt.y) || 1, dist = b * R * (.2 + .5 * p.o);
      x = tx + p.pt.x / len * dist; y = ty + p.pt.y / len * dist;
      size = u * .7 * p.s * (1 - .6 * b); alpha = 1 - seg(t, 3.9, 5.0); rot = 0; light = 68;
    }
    if (alpha <= 0 || size <= 0) continue;
    ctx.save(); ctx.globalAlpha *= alpha; ctx.translate(x, y); ctx.rotate(rot);
    ctx.fillStyle = `hsl(${lerp(p.hue, 38, am)} ${lerp(62, 95, am)}% ${light}%)`;
    ctx.beginPath(); ctx.roundRect(-size / 2, -size * .28, size, size * .5625, size * .12); ctx.fill(); ctx.restore();
  }
  if (t >= 3.66) {
    const slide = eio(seg(t, 4.3, 5.0)), tx = lerp(cx, cx - lk.total / 2 + ts / 2, slide);
    const rp = seg(t, 3.72, 4.6); if (rp < 1) ring(ctx, cx, cy, ts * (.5 + 2.2 * eo3(rp)), Math.max(1, u * .7 * (1 - rp)), (1 - rp) * .9);
    drawWord(ctx, tx + ts / 2 + lk.gap, cy, fs, { fx: l => { const e = eo3(seg(t, 4.35 + l.i * .045, 5.0 + l.i * .045)); return { a: e, dx: (l.i - 3.5) * fs * .3 * (1 - e) }; } });
    tile(ctx, tx, cy, ts * eback(seg(t, 3.66, 4.05)), { cross: seg(t, 4.0, 4.2) });
    const ta = eo3(seg(t, 5.2, 5.7));
    text(ctx, 'Hours of footage. One spark.', cx, cy + fs * 1.5 + fs * .3 * (1 - ta), fs * .34, '#b8ada0', ta);
  }
  ctx.globalAlpha = 1;
}

/* ---------- F4 Caption Beat ---------- */
const SMALL = document.createElement('canvas'), SCTX = SMALL.getContext('2d');
// ``o.layer`` draws only the see-through card: the render blurs the clip's own
// last frame underneath it, so the sample scene is left out.
function F4(ctx, W, H, t, T, o = {}) {
  const m = Math.min(W, H), u = m / 100, fs = m * .1, cx = W / 2, cy = H / 2, lk = lockup(ctx, fs), ts = lk.ts;
  const b = eio(seg(t, 0, .9));
  if (o.layer) {
    ctx.fillStyle = `rgba(8,7,6,${.62 * b})`; ctx.fillRect(0, 0, W, H);
  } else {
    scene(ctx, 0, 0, W, H, 170, t + 3);
    const sw = 40, sh = Math.max(2, Math.round(40 * H / W));
    SMALL.width = sw; SMALL.height = sh; SCTX.setTransform(sw / W, 0, 0, sh / H, 0, 0); scene(SCTX, 0, 0, W, H, 170, t + 3);
    ctx.save(); ctx.globalAlpha = b; ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(SMALL, 0, 0, W, H); ctx.fillStyle = 'rgba(8,7,6,.62)'; ctx.fillRect(0, 0, W, H); ctx.restore();
  }

  const bt = t - 1.8, pulse = bt > 0 ? Math.exp(-(bt % .5) * 9) : 0;
  const y0 = H * (H > W ? .8 : .84);
  ctx.save(); ctx.globalAlpha = .5 * b; ctx.strokeStyle = AMBER; ctx.lineWidth = Math.max(1, u * .35); ctx.lineJoin = 'round';
  ctx.beginPath();
  for (let i = 0; i <= 120; i++) {
    const x = W * i / 120, env = Math.sin(Math.PI * i / 120);
    const y = y0 + (Math.sin(i / 120 * 14 + t * 6) * u * 2.4 * (.3 + pulse) + Math.sin(i / 120 * 31 - t * 9) * u * 1.1 * (.3 + pulse)) * env;
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  }
  ctx.stroke(); ctx.restore();

  const words = [['MADE', .8], ['WITH', 1.3]], csz = fs * .46, cyc = cy - fs * 1.35;
  ctx.font = `800 ${csz}px "Plus Jakarta Sans", sans-serif`;
  const wm = words.map(([w]) => ctx.measureText(w).width), gap = csz * .45, start = cx - (wm[0] + gap + wm[1]) / 2;
  const pos = [start, start + wm[0] + gap];
  const pp = eio(seg(t, 1.3, 1.42)), pa = seg(t, .8, .9) * (1 - seg(t, 1.8, 2.0));
  if (pa > 0) {
    ctx.save(); ctx.globalAlpha = pa;
    pill(ctx, lerp(pos[0], pos[1], pp) - csz * .3, cyc - csz * .72, lerp(wm[0], wm[1], pp) + csz * .6, csz * 1.44, AMBER); ctx.restore();
  }
  words.forEach(([w, st], i) => {
    const e = seg(t, st, st + .28), lit = pa > .5 && (i === 0 ? pp < .5 : pp >= .5);
    if (t < st) return;
    ctx.save(); ctx.translate(pos[i] + wm[i] / 2, cyc); const s = lerp(1.45, 1, eback(e)); ctx.scale(s, s);
    text(ctx, w, 0, 0, csz, lit ? INK : '#fff', 1, 800);
    ctx.restore();
  });

  if (t >= 1.8) {
    const land = seg(t, 1.8, 2.15), S = lerp(1.7, 1, eback(land)) * (1 + .02 * pulse);
    const dx = Math.sin(t * 90) * u * .7 * (1 - seg(t, 1.9, 2.3)) * (t > 1.9 ? 1 : 0);
    const tx = cx - lk.total / 2 + ts / 2;
    ctx.save(); ctx.globalAlpha = seg(t, 1.8, 1.88); ctx.translate(cx + dx, cy); ctx.scale(S, S); ctx.translate(-cx, -cy);
    if (bt > .4) ring(ctx, tx, cy, ts * (.6 + .9 * ((bt % .5) / .5)), Math.max(1, u * .4), pulse * .5);
    drawWord(ctx, tx + ts / 2 + lk.gap, cy, fs);
    tile(ctx, tx, cy, ts, { starScale: 1 + .22 * pulse });
    ctx.restore();
  }
  const ca = eo3(seg(t, 2.7, 3.2));
  if (ca > 0) {
    const csz2 = fs * .34, label = 'Turn long videos into shorts';
    ctx.font = `600 ${csz2}px "Plus Jakarta Sans", sans-serif`;
    const w = ctx.measureText(label).width, y = cy + fs * 1.6 + fs * .3 * (1 - ca);
    ctx.save(); ctx.globalAlpha = ca;
    pill(ctx, cx - w / 2 - csz2, y - csz2 * 1.1, w + csz2 * 2, csz2 * 2.2, 'rgba(245,158,11,.16)', 'rgba(245,158,11,.6)');
    ctx.restore();
    text(ctx, label, cx, y, csz2, '#fff', ca);
  }
  const fade = seg(t, 6.0, 6.5);
  if (fade > 0) { ctx.fillStyle = `rgba(11,10,9,${fade})`; ctx.fillRect(0, 0, W, H); }
}

/* ---------- watermarks ---------- */
function geo(ctx, W, H, extraF = 0, insetF = 0) {
  const m = Math.min(W, H), fs = m * .05, lk = lockup(ctx, fs), margin = m * .055 + insetF * fs;
  const total = lk.total + extraF * fs, right = W - margin, left = right - total, cy = margin + lk.ts / 2;
  return { m, fs, lk, cy, left, right, total, tileX: left + lk.ts / 2, wordX: left + lk.ts + lk.gap };
}
function shade(ctx, fs) { ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = fs * .5 * DPR; ctx.shadowOffsetY = fs * .06 * DPR; }
function glow(ctx, fs, k) { ctx.shadowColor = `rgba(245,158,11,${.95 * k})`; ctx.shadowBlur = fs * 1.4 * k * DPR; ctx.shadowOffsetY = 0; }

function voice(T) {
  const gate = Math.sin(T * .9 + .5) > -.55 ? 1 : 0;
  const s = Math.max(0, Math.sin(T * 10.5)) * Math.max(0, Math.sin(T * 2.1 + .4) + .35);
  return cl(s * (.75 + .25 * Math.abs(Math.sin(T * 23.7))) * gate);
}
// Listening Spark: each level bar trails the one before it by this long.
const SPARK_BAR_LAG = .09;
const sparkBarX = (g, k) => g.wordX + g.lk.ww + g.fs * .3 + k * g.fs * .22;
function sparkBar(ctx, g, x, e) {
  const h = g.fs * (.22 + .62 * e);
  ctx.fillStyle = AMBER; ctx.beginPath(); ctx.roundRect(x, g.cy - h / 2, g.fs * .12, h, g.fs * .06); ctx.fill();
}
function sparkTile(ctx, g, e) { glow(ctx, g.fs, e); tile(ctx, g.tileX, g.cy, g.lk.ts, { starScale: 1 + .3 * e }); }
function W1(ctx, W, H, t, T) {
  const g = geo(ctx, W, H, .86);
  ctx.save(); shade(ctx, g.fs); drawWord(ctx, g.wordX, g.cy, g.fs);
  for (let k = 0; k < 3; k++) sparkBar(ctx, g, sparkBarX(g, k), voice(T - k * SPARK_BAR_LAG));
  sparkTile(ctx, g, voice(T));
  ctx.restore();
}
// Listening Spark cut into the pieces the server stacks per frame from the
// clip's own loudness: the name, the tile at each level and one level bar at
// each height. Offsets are inside the overlay box, at a 1080px short side.
function sparkSprites(levels) {
  const REF = 1080, c = document.createElement('canvas'), ctx = c.getContext('2d');
  const g = geo(ctx, REF, REF, .86), pad = Math.ceil(g.fs * 1.6), pad2 = Math.ceil(g.fs * .8);
  const rect = (x0, y0, x1, y1) => ({ x: Math.floor(x0), y: Math.floor(y0), w: Math.ceil(x1) - Math.floor(x0), h: Math.ceil(y1) - Math.floor(y0) });
  const box = rect(g.left - pad, g.cy - g.lk.ts / 2 - pad, g.right + pad, g.cy + g.lk.ts / 2 + pad);
  const shot = (r, draw) => {
    c.width = r.w; c.height = r.h;
    ctx.setTransform(1, 0, 0, 1, -r.x, -r.y); ctx.save(); draw(); ctx.restore();
    return { png: c.toDataURL('image/png'), x: r.x - box.x, y: r.y - box.y };
  };
  const wordRect = rect(g.wordX - pad2, g.cy - g.fs - pad2, g.wordX + g.lk.ww + pad2, g.cy + g.fs + pad2);
  const tileRect = rect(g.tileX - g.lk.ts / 2 - pad, g.cy - g.lk.ts / 2 - pad, g.tileX + g.lk.ts / 2 + pad, g.cy + g.lk.ts / 2 + pad);
  const x0 = sparkBarX(g, 0), barRect = rect(x0 - pad2, g.cy - g.fs * .42 - pad2, x0 + g.fs * .12 + pad2, g.cy + g.fs * .42 + pad2);
  const level = i => i / (levels - 1);
  const bars = Array.from({ length: levels }, (_, i) => shot(barRect, () => { shade(ctx, g.fs); sparkBar(ctx, g, x0, level(i)); }));
  return {
    ref: REF, levels, bar_lag_s: SPARK_BAR_LAG,
    box: { w: box.w, h: box.h }, anchor: { right: REF - box.x, top: box.y },
    word: shot(wordRect, () => { shade(ctx, g.fs); drawWord(ctx, g.wordX, g.cy, g.fs); }),
    tiles: Array.from({ length: levels }, (_, i) => shot(tileRect, () => sparkTile(ctx, g, level(i)))),
    bars, bar_x: [0, 1, 2].map(k => bars[0].x + Math.round(sparkBarX(g, k) - x0)),
  };
}
function W2(ctx, W, H, t) {
  const g = geo(ctx, W, H), a = eio(seg(t, .2, 1.3)) * Math.PI * 2, c = Math.cos(a);
  ctx.save(); shade(ctx, g.fs); drawWord(ctx, g.wordX, g.cy, g.fs);
  tile(ctx, g.tileX, g.cy, g.lk.ts, { sx: Math.max(.03, Math.abs(c)), fill: c < 0 ? '#b45309' : AMBER, star: c < 0 ? 0 : 1 });
  ctx.restore();
  const sp = seg(t, 1.25, 2.1);
  if (sp > 0 && sp < 1) {
    const bx = lerp(g.left - g.fs * 1.5, g.right + g.fs * 1.5, eio(sp));
    ctx.save(); ctx.globalCompositeOperation = 'source-atop';
    const gr = ctx.createLinearGradient(bx - g.fs, g.cy - g.fs, bx + g.fs, g.cy + g.fs);
    gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(.5, 'rgba(255,255,255,.8)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gr; ctx.fillRect(g.left - g.fs, g.cy - g.fs * 1.5, g.total + g.fs * 2, g.fs * 3); ctx.restore();
  }
}
function W3(ctx, W, H, t, T) {
  const g = geo(ctx, W, H, 0, .55), pd = g.fs * (.45 + .06 * Math.sin(T * 2)), arm = g.fs * .4;
  const L = g.left - pd, R = g.right + pd, Tp = g.cy - g.lk.ts / 2 - pd, B = g.cy + g.lk.ts / 2 + pd;
  ctx.save(); shade(ctx, g.fs); drawWord(ctx, g.wordX, g.cy, g.fs); tile(ctx, g.tileX, g.cy, g.lk.ts);
  ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = Math.max(1, g.fs * .09); ctx.lineCap = 'round';
  ctx.beginPath();
  for (const [px, py, dx, dy] of [[L, Tp, 1, 1], [R, Tp, -1, 1], [L, B, 1, -1], [R, B, -1, -1]]) { ctx.moveTo(px + dx * arm, py); ctx.lineTo(px, py); ctx.lineTo(px, py + dy * arm); }
  ctx.stroke();
  const f = Math.floor(T * 30), tc = `00:${pad2(Math.floor(T / 60) % 60)}:${pad2(Math.floor(T) % 60)}:${pad2(f % 30)}`, tsz = g.fs * .42, ty = B + g.fs * .55;
  text(ctx, tc, R, ty, tsz, 'rgba(255,255,255,.9)', 1, 500, 'mono', 'right');
  ctx.font = `500 ${tsz}px "JetBrains Mono", monospace`;
  const tw = ctx.measureText(tc).width;
  if (T % 1 < .6) { ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(R - tw - tsz * .7, ty, tsz * .28, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
}
function W4(ctx, W, H, t) {
  const g = geo(ctx, W, H), sp = seg(t, .4, 1.5), scanX = lerp(g.left - g.fs * .3, g.right + g.fs * .3, eio(sp));
  const q = seg(t, 1.45, 1.95), tw = bump(q);
  ctx.save(); shade(ctx, g.fs);
  drawWord(ctx, g.wordX, g.cy, g.fs, {
    fx: l => {
      const k = (scanX - (g.wordX + l.x + l.w / 2)) / (g.fs * 1.3);
      if (sp <= 0 || k <= 0 || k >= 1) return {};
      return { color: l.nera ? '#fff' : AMBER, dy: -g.fs * .16 * Math.sin(Math.PI * k) };
    }
  });
  if (tw > 0) glow(ctx, g.fs, tw);
  tile(ctx, g.tileX, g.cy, g.lk.ts, { starScale: 1 + .3 * tw, starRot: q * Math.PI / 2 });
  ctx.restore();
  if (sp > 0 && sp < 1) {
    ctx.save(); const h = g.lk.ts * 1.6;
    const gr = ctx.createLinearGradient(scanX - g.fs * .8, 0, scanX + g.fs * .2, 0);
    gr.addColorStop(0, 'rgba(245,158,11,0)'); gr.addColorStop(1, 'rgba(245,158,11,.35)');
    ctx.fillStyle = gr; ctx.fillRect(scanX - g.fs * .8, g.cy - h / 2, g.fs, h);
    ctx.fillStyle = AMBER; ctx.fillRect(scanX, g.cy - h / 2, Math.max(1.5, g.fs * .08), h);
    ctx.restore();
  }
}
function W5(ctx, W, H, t) {
  const g = geo(ctx, W, H), ls = letters(ctx, g.fs), clipEnd = ls[3].x + ls[3].w, neraX = ls[4].x, ww = wordWidth(ls);
  const pa = seg(t, .1, .25) * (1 - seg(t, 1.5, 1.8)), p = eio(seg(t, .75, 1.0));
  ctx.save(); shade(ctx, g.fs);
  if (pa > 0) {
    ctx.save(); ctx.globalAlpha *= pa;
    pill(ctx, g.wordX + lerp(0, neraX, p) - g.fs * .16, g.cy - g.fs * .64, lerp(clipEnd, ww - neraX, p) + g.fs * .32, g.fs * 1.28, AMBER);
    ctx.restore();
  }
  drawWord(ctx, g.wordX, g.cy, g.fs, {
    fx: l => {
      const lit = pa > .5 && (l.nera ? p >= .5 : p < .5);
      return { color: lit ? INK : undefined, s: 1 + .2 * bump(seg(t, l.nera ? .75 : .1, l.nera ? 1.1 : .45)) };
    }
  });
  tile(ctx, g.tileX, g.cy, g.lk.ts);
  ctx.restore();
}
function W6(ctx, W, H, t) {
  const g = geo(ctx, W, H), lcx = g.left + g.total / 2, rx = g.total / 2 + g.fs * .55, ry = g.lk.ts / 2 + g.fs * .5;
  const posAt = tau => {
    const th = Math.PI + eio(seg(tau, .2, 2.3)) * Math.PI * 2, dv = eio(seg(tau, 2.1, 2.5));
    return [lerp(lcx + rx * Math.cos(th), g.tileX, dv), lerp(g.cy + ry * Math.sin(th), g.cy, dv)];
  };
  const fl = bump(seg(t, 2.45, 3.0));
  ctx.save(); shade(ctx, g.fs); drawWord(ctx, g.wordX, g.cy, g.fs);
  if (fl > 0) glow(ctx, g.fs, fl);
  tile(ctx, g.tileX, g.cy, g.lk.ts, { starScale: 1 + .35 * fl, starRot: fl * .8 });
  ctx.restore();
  const vis = seg(t, .2, .35) * (1 - seg(t, 2.45, 2.55));
  if (vis > 0) {
    ctx.save();
    for (let k = 16; k >= 0; k--) {
      const tau = t - k * .025; if (tau < .2) continue;
      const [x, y] = posAt(tau), f = 1 - k / 17;
      ctx.globalAlpha = vis * f * .9; ctx.fillStyle = k ? AMBER : '#fff';
      if (!k) { ctx.shadowColor = AMBER; ctx.shadowBlur = g.fs * .8 * DPR; }
      ctx.beginPath(); ctx.arc(x, y, g.fs * (k ? .13 * f : .14), 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
  }
}

