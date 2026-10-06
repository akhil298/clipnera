/* Clipnera motion templates: the graphics the director lays over a clip.
 * Each one draws a frame of its own slot box, on a transparent canvas, as a pure function of time
 * and the fields the director filled in, so any frame renders on its own and the same spec always
 * gives the same clip. Loaded by motion.html after kit.js, whose easing and drawing helpers it
 * reuses; `render.mjs motion` turns the frames into PNG-in-MOV clips. */

// Every graphic eases in over IN_S and out over the last OUT_S of its duration.
const IN_S = .35, OUT_S = .3;
const WHITE = '#fafaf9', PANEL = 'rgba(12,10,9,.86)';
const SANS = '"Plus Jakarta Sans", sans-serif', DISPLAY = 'Syne, sans-serif';

/** How far the graphic has come in and gone out at ``t``, each 0-1. */
const phase = (t, dur) => ({ come: seg(t, 0, IN_S), go: seg(t, dur - OUT_S, dur) });

/** The largest font size up to ``max`` at which ``s`` fits in ``maxW``. */
function fit(ctx, s, weight, family, maxW, max) {
  ctx.font = `${weight} ${max}px ${family}`;
  return Math.min(max, max * maxW / Math.max(1, ctx.measureText(s).width));
}

function label(ctx, s, x, y, size, color, weight, family, align = 'center') {
  ctx.font = `${weight} ${size}px ${family}`;
  ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = 'middle';
  ctx.fillText(s, x, y);
}

function circle(ctx, x, y, r, lw, color, alpha) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = color; ctx.lineWidth = lw;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
}

function shadow(ctx, size) {
  ctx.shadowColor = 'rgba(0,0,0,.55)'; ctx.shadowBlur = size * .35; ctx.shadowOffsetY = size * .05;
}

/** ``value`` shown with ``decimals`` places and the locale's digit grouping. */
function formatNumber(value, decimals, locale = 'en-US') {
  return value.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/** The dark rounded panel most templates sit on, with an accent edge when ``accent`` is given. */
function card(ctx, x, y, w, h, r, accent = null, lw = 0) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, r);
  ctx.fillStyle = PANEL; ctx.fill();
  if (accent) { ctx.lineWidth = lw; ctx.strokeStyle = accent; ctx.stroke(); }
}

/** A rounded bar, never narrower than it is tall once it has any length at all. */
function bar(ctx, x, y, w, h, color) {
  if (w <= 0) return;
  ctx.beginPath(); ctx.roundRect(x, y, Math.max(h, w), h, h / 2);
  ctx.fillStyle = color; ctx.fill();
}

/** Moves the origin to (cx, cy), then pops in and shrinks out about it. Call between save and restore. */
function popIn(ctx, come, go, cx, cy) {
  const s = eback(come) * (1 - .15 * eo3(go));
  ctx.globalAlpha *= Math.min(1, come * 2) * (1 - go);
  ctx.translate(cx, cy); ctx.scale(s, s);
}

/** ``text`` broken into lines no wider than ``maxW`` at the current font. */
function wrap(ctx, text, maxW) {
  const lines = [];
  let line = '';
  for (const word of String(text).split(/\s+/)) {
    const next = line ? `${line} ${word}` : word;
    if (line && ctx.measureText(next).width > maxW) { lines.push(line); line = word; } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

/* ---------- count-up: a spoken number that matters ---------- */
function countUp(ctx, W, H, t, dur, f, accent) {
  const { come, go } = phase(t, dur);
  if (come <= 0 || go >= 1) return;
  const value = Number(f.value), decimals = Number(f.decimals ?? 0);
  // The count runs over most of the hold, easing out so the final value lands and stays.
  const shown = value * eo3(seg(t, IN_S * .5, Math.min(dur - OUT_S, IN_S + .9)));
  const digits = `${f.prefix ?? ''}${formatNumber(shown, decimals, f.locale)}${f.suffix ?? ''}`;
  const final = `${f.prefix ?? ''}${formatNumber(value, decimals, f.locale)}${f.suffix ?? ''}`;
  const pad = H * .1, numSize = fit(ctx, final, 800, DISPLAY, W - 4 * pad, H * .46);
  const labelSize = f.label ? fit(ctx, f.label, 700, SANS, W - 4 * pad, H * .13) : 0;
  ctx.font = `800 ${numSize}px ${DISPLAY}`;
  const numW = ctx.measureText(final).width;
  ctx.font = `700 ${labelSize}px ${SANS}`;
  const boxW = Math.max(numW, f.label ? ctx.measureText(f.label).width : 0) + 4 * pad;
  const boxH = numSize * 1.15 + (f.label ? labelSize * 1.6 : 0) + 1.2 * pad;
  ctx.save();
  popIn(ctx, come, go, W / 2, H / 2);
  card(ctx, -boxW / 2, -boxH / 2, boxW, boxH, pad * .9, accent, Math.max(2, H * .008));
  const numY = -boxH / 2 + .6 * pad + numSize * .58;
  label(ctx, digits, 0, numY, numSize, accent, 800, DISPLAY);
  if (f.label) label(ctx, f.label, 0, numY + numSize * .62 + labelSize * .7, labelSize, WHITE, 700, SANS);
  ctx.restore();
}

/* ---------- lower-third: a person, brand or tool being introduced ---------- */
function lowerThird(ctx, W, H, t, dur, f, accent) {
  const { come, go } = phase(t, dur);
  if (come <= 0 || go >= 1) return;
  const x0 = W * .04, barW = W * .018, nameSize = fit(ctx, f.name, 800, SANS, W * .86, H * .34);
  const roleSize = f.role ? fit(ctx, f.role, 600, SANS, W * .86, H * .19) : 0;
  const textH = nameSize + (f.role ? roleSize * 1.35 : 0), top = (H - textH) / 2;
  // The bar grows first, then the text slides out from behind it; going out reverses both.
  const grow = eo3(seg(t, 0, IN_S)) * (1 - eo3(seg(t, dur - OUT_S * .4, dur)));
  const slide = eo3(seg(t, IN_S * .45, IN_S * 1.6)) * (1 - eio(seg(t, dur - OUT_S, dur - OUT_S * .35)));
  ctx.save();
  ctx.fillStyle = accent;
  ctx.fillRect(x0, top + textH * (1 - grow) / 2, barW, textH * grow);
  ctx.beginPath(); ctx.rect(x0 + barW, 0, W, H); ctx.clip();
  const dx = (1 - slide) * -W * .6, tx = x0 + barW * 2.2 + dx;
  ctx.globalAlpha = slide;
  ctx.font = `800 ${nameSize}px ${SANS}`;
  const nameW = ctx.measureText(f.name).width;
  ctx.font = `600 ${roleSize}px ${SANS}`;
  const panelW = Math.max(nameW, f.role ? ctx.measureText(f.role).width : 0);
  ctx.fillStyle = PANEL;
  ctx.fillRect(x0 + barW + dx, top - H * .06, panelW + barW * 3.4, textH + H * .12);
  shadow(ctx, nameSize);
  label(ctx, f.name, tx, top + nameSize * .52, nameSize, WHITE, 800, SANS, 'left');
  if (f.role) label(ctx, f.role, tx, top + nameSize + roleSize * .78, roleSize, accent, 600, SANS, 'left');
  ctx.restore();
}

/* ---------- keyword-slam: the one word a line hangs on ---------- */
function keywordSlam(ctx, W, H, t, dur, f, accent) {
  const { come, go } = phase(t, dur);
  if (come <= 0 || go >= 1) return;
  // Sized so the word still fits its box at the start of the slam, when it is drawn largest.
  const START = 1.4, word = String(f.word).toUpperCase();
  const size = fit(ctx, word, 800, DISPLAY, W * .8 / START, H * .5 / START);
  // Slams down from START, lands with a short shake, then the slab wipes in behind it.
  const land = seg(t, 0, IN_S * .7), s = lerp(START, 1, eo3(land)) * (1 + .08 * eo3(go));
  const shake = land >= 1 ? Math.sin(t * 90) * size * .03 * (1 - seg(t, IN_S * .7, IN_S * 1.5)) : 0;
  const slab = eo3(seg(t, IN_S * .55, IN_S * 1.3));
  ctx.save();
  ctx.globalAlpha = Math.min(1, land * 3) * (1 - go);
  ctx.translate(W / 2 + shake, H / 2); ctx.scale(s, s);
  ctx.font = `800 ${size}px ${DISPLAY}`;
  const w = ctx.measureText(word).width, slabH = size * .92;
  const slabPath = new Path2D();
  slabPath.rect(-w / 2 - size * .25, -slabH / 2, (w + size * .5) * slab, slabH);
  ctx.save(); ctx.transform(1, 0, -.18, 1, 0, 0);
  ctx.fillStyle = accent; ctx.fill(slabPath);
  ctx.restore();
  ctx.save(); shadow(ctx, size);
  label(ctx, word, 0, size * .04, size, WHITE, 800, DISPLAY);
  ctx.restore();
  // Where the slab has wiped in, the word turns dark so it reads on the accent.
  ctx.transform(1, 0, -.18, 1, 0, 0); ctx.clip(slabPath); ctx.transform(1, 0, .18, 1, 0, 0);
  label(ctx, word, 0, size * .04, size, INK, 800, DISPLAY);
  ctx.restore();
  // A ring kicks out from the landing point.
  const kick = seg(t, IN_S * .7, IN_S * 2);
  // The ring stays inside the box: a ring cut by the box edge shows as two stray arcs.
  if (land >= 1) circle(ctx, W / 2, H / 2, lerp(H * .2, H * .47, eo3(kick)), H * .015, accent, .7 * (1 - kick));
}

/* ---------- callout-arrow: points at something on screen ---------- */
function calloutArrow(ctx, W, H, t, dur, f, accent) {
  const { come, go } = phase(t, dur);
  if (come <= 0 || go >= 1) return;
  // The target is a fraction of the box; the label sits in the opposite half, so the arrow
  // always has room to travel.
  const tx = Number(f.tx ?? .7) * W, ty = Number(f.ty ?? .35) * H;
  const lx = tx > W / 2 ? W * .3 : W * .7, ly = ty > H / 2 ? H * .22 : H * .78;
  const size = fit(ctx, f.label, 800, SANS, W * .5, Math.min(W, H) * .085);
  ctx.font = `800 ${size}px ${SANS}`;
  const pw = ctx.measureText(f.label).width + size * 1.4, ph = size * 1.8;
  const alpha = (1 - go);
  ctx.save(); ctx.globalAlpha = alpha;
  // Label pops in, then the arrow draws from it to the target, then the target pulses.
  const pop = eback(seg(t, 0, IN_S));
  ctx.save(); ctx.translate(lx, ly); ctx.scale(pop, pop);
  shadow(ctx, size); pill(ctx, -pw / 2, -ph / 2, pw, ph, accent);
  ctx.shadowColor = 'transparent';
  label(ctx, f.label, 0, size * .05, size, INK, 800, SANS);
  ctx.restore();
  const sx = lx + Math.sign(tx - lx) * pw * .2, sy = ly + Math.sign(ty - ly) * ph * .5;
  const ang = Math.atan2(ty - sy, tx - sx), dist = Math.hypot(tx - sx, ty - sy) - size * .9;
  const ex = sx + Math.cos(ang) * dist, ey = sy + Math.sin(ang) * dist;
  // A slight bend reads as hand-placed rather than a ruler line.
  const cx = (sx + ex) / 2 - Math.sin(ang) * dist * .18, cy = (sy + ey) / 2 + Math.cos(ang) * dist * .18;
  const draw = eio(seg(t, IN_S * .6, IN_S * 1.8));
  const len = dist * 1.05;
  ctx.lineWidth = size * .22; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = accent;
  shadow(ctx, size * .6);
  ctx.setLineDash([len * draw, len]);
  ctx.beginPath(); ctx.moveTo(sx, sy); ctx.quadraticCurveTo(cx, cy, ex, ey); ctx.stroke();
  ctx.setLineDash([]);
  if (draw >= 1) {
    const head = size * .75, a = Math.atan2(ey - cy, ex - cx);
    ctx.beginPath();
    ctx.moveTo(ex - Math.cos(a - .5) * head, ey - Math.sin(a - .5) * head);
    ctx.lineTo(ex, ey);
    ctx.lineTo(ex - Math.cos(a + .5) * head, ey - Math.sin(a + .5) * head);
    ctx.stroke();
  }
  ctx.restore();
  const pulse = seg(t, IN_S * 1.8, IN_S * 1.8 + .6);
  if (pulse > 0) {
    circle(ctx, tx, ty, size * lerp(.6, 1.6, eo3(pulse)), size * .14, accent, alpha * (1 - pulse));
    circle(ctx, tx, ty, size * .55, size * .12, accent, alpha);
  }
}

/** Template id -> its drawing function and the fields it cannot do without. */
const TEMPLATES = {
  'count-up': { draw: countUp, requires: ['value'] },
  'lower-third': { draw: lowerThird, requires: ['name'] },
  'keyword-slam': { draw: keywordSlam, requires: ['word'] },
  'callout-arrow': { draw: calloutArrow, requires: ['label'] },
};
