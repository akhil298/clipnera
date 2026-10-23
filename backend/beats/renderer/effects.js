// Signature effects (reel_engine/effects.py, data/effects.json): one template, `effect`, drawing the effect named in
// s.data.effect. Split effects come as two beats, part "back" (under the speaker's cut-out) and part "front";
// both compute the same geometry so they line up. Opaque back parts replace the background. Everything is drawn
// here in code: no stock art, so nothing to license.
(() => {
  const { T, el, boxed, fitText, ease, span, clamp, EXIT } = window.BeatsKit;
  const SVG = 'http://www.w3.org/2000/svg';
  const W = 1080, H = 1920;

  function rand(seed) {
    let s = [...String(seed)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 2166136261);
    return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  }
  const fade = (t, dur, inT = 0.25) => clamp(span(t, 0, inT)) * (1 - ease.out(span(t, dur - EXIT, EXIT)));
  const full = (root, cls = '') => {
    const d = el('div', `full ${cls}`, root);
    d.style.overflow = 'hidden';
    return d;
  };
  const faceOf = (s) => {
    const [x0, y0, x1, y1] = s.data.face || [W * 0.3, H * 0.25, W * 0.7, H * 0.45];
    return { x0, y0, x1, y1, w: x1 - x0, h: y1 - y0, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 };
  };
  const svgEl = (tag, attrs, parent) => {
    const n = document.createElementNS(SVG, tag);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  };

  // ---------------------------------------------------------------- Doodle Boy: marker doodles drawn on around the face
  function doodlePaths(choice, target, f) {
    const r = Math.max(f.w, f.h) * 0.62;
    // The face box starts at the brows; the top of the head (or a cap) sits about half a face higher.
    const top = Math.max(140, f.y0 - f.h * 0.55);
    const P = [];
    const star = (x, y, s) => `M${x},${y - s} L${x + s * 0.28},${y - s * 0.28} L${x + s},${y} L${x + s * 0.28},${y + s * 0.28} L${x},${y + s} L${x - s * 0.28},${y + s * 0.28} L${x - s},${y} L${x - s * 0.28},${y - s * 0.28} Z`;
    if (choice === 'crown') {
      const w = f.w * 0.8, x = f.cx - w / 2, y = top, k = Math.min(f.h * 0.42, top - 40);
      P.push(`M${x},${y} L${x + w * 0.08},${y - k} L${x + w * 0.3},${y - k * 0.38} L${x + w * 0.5},${y - k * 1.15} L${x + w * 0.7},${y - k * 0.38} L${x + w * 0.92},${y - k} L${x + w},${y} Z`);
    } else if (choice === 'circle' || target === 'face_around') {
      P.push(`M${f.cx + r},${f.cy} C${f.cx + r},${f.cy - r * 1.15} ${f.cx - r},${f.cy - r * 1.2} ${f.cx - r * 1.02},${f.cy} C${f.cx - r},${f.cy + r * 1.2} ${f.cx + r * 1.05},${f.cy + r * 1.1} ${f.cx + r * 0.96},${f.cy - r * 0.25}`);
    } else if (choice === 'arrow' || target === 'point_left' || target === 'point_right') {
      const left = target !== 'point_right';
      const sx = left ? Math.max(60, f.x0 - r * 1.3) : Math.min(W - 60, f.x1 + r * 1.3), sy = f.cy + r * 0.9;
      const ex = left ? f.x0 - 24 : f.x1 + 24, ey = f.cy + f.h * 0.1;
      const mx = (sx + ex) / 2, my = Math.max(sy, ey) + r * 0.35;
      P.push(`M${sx},${sy} Q${mx},${my} ${ex},${ey}`);
      const d = left ? -1 : 1;
      P.push(`M${ex + d * 46},${ey - 22} L${ex},${ey} L${ex + d * 30},${ey + 44}`);
    } else if (choice === 'underline' || target === 'below_face') {
      const y = f.y1 + f.h * 0.22, x = f.cx - f.w * 0.65, w = f.w * 1.3;
      P.push(`M${x},${y} C${x + w * 0.3},${y - 26} ${x + w * 0.6},${y + 22} ${x + w},${y - 10}`);
      P.push(`M${x + w * 0.12},${y + 30} C${x + w * 0.4},${y + 12} ${x + w * 0.7},${y + 40} ${x + w * 0.92},${y + 22}`);
    } else if (choice === 'heart') {
      const x = f.x1 + 20, y = top + 10, s = f.w * 0.32;
      P.push(`M${x},${y + s * 0.3} C${x},${y - s * 0.4} ${x - s},${y - s * 0.3} ${x - s * 0.5},${y + s * 0.5} L${x},${y + s} L${x + s * 0.5},${y + s * 0.5} C${x + s},${y - s * 0.3} ${x},${y - s * 0.4} ${x},${y + s * 0.3}`);
    } else if (choice === 'question' || choice === 'exclaim') {
      const x = f.x1 + f.w * 0.15, y = top - f.h * 0.25, s = f.h * 0.55;
      if (choice === 'question') P.push(`M${x - s * 0.3},${y + s * 0.15} C${x - s * 0.3},${y - s * 0.3} ${x + s * 0.4},${y - s * 0.3} ${x + s * 0.35},${y + s * 0.15} C${x + s * 0.3},${y + s * 0.45} ${x},${y + s * 0.4} ${x},${y + s * 0.7}`);
      else P.push(`M${x},${y - s * 0.2} L${x},${y + s * 0.62}`);
      P.push(`M${x},${y + s * 0.95} L${x + 2},${y + s * 0.99}`);
    } else if (choice === 'lightning') {
      const x = f.x1 + f.w * 0.2, y = f.cy - f.h * 0.6, s = f.h * 0.9;
      P.push(`M${x + s * 0.15},${y} L${x - s * 0.15},${y + s * 0.5} L${x + s * 0.12},${y + s * 0.5} L${x - s * 0.2},${y + s}`);
    } else {  // sparkles / stars
      const n = choice === 'stars' ? 3 : 4;
      for (let i = 0; i < n; i++) {
        const a = -Math.PI * (0.15 + 0.7 * (i / (n - 1)));
        P.push(star(f.cx + Math.cos(a) * r * 1.05, f.cy + Math.sin(a) * r * 1.05, f.w * (i % 2 ? 0.1 : 0.15)));
      }
    }
    return P;
  }

  function doodle(s, root) {
    const f = faceOf(s);
    const svg = svgEl('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, root);
    Object.assign(svg.style, { position: 'absolute', left: 0, top: 0, overflow: 'visible', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,.55))' });
    const paths = doodlePaths(s.data.choice, s.data.target, f).map((d, i) => {
      const p = svgEl('path', { d, fill: 'none', 'stroke-width': 13, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, svg);
      p.style.stroke = !i && (s.data.choice === 'crown' || s.data.choice === 'heart') ? 'var(--accent)' : '#fff';
      const len = p.getTotalLength();
      p.style.strokeDasharray = `${len}`;
      return { p, len, at: 0.05 + i * 0.18 };
    });
    return {
      seek(t) {
        svg.style.opacity = fade(t, s.dur, 0.05);
        // Hand-drawn boil: the doodle jitters a pixel or two, a few times a second.
        const step = Math.floor(t * 8);
        svg.style.transform = `translate(${(step % 3) - 1}px, ${((step * 7) % 3) - 1}px)`;
        paths.forEach(({ p, len, at }) => { p.style.strokeDashoffset = `${len * (1 - ease.out(span(t, at, 0.42)))}`; });
      },
    };
  }

  // ---------------------------------------------------------------- Headline Wall: a newspaper of headlines behind the speaker
  function headlineWall(s, root) {
    const page = full(root);
    page.style.background = '#f2eee4';
    const r = rand(s.data.texts.join('|'));
    const rows = [];
    let y = 40, k = 0;
    while (y < H + 200) {
      const text = s.data.texts[k % s.data.texts.length];
      const size = [120, 84, 150, 96, 70][k % 5];
      const row = el('div', '', page, k % 3 === 2 ? text.toUpperCase() : text);
      Object.assign(row.style, { position: 'absolute', left: `${-40 + r() * 60}px`, top: `${y}px`, width: `${W + 80}px`, whiteSpace: 'nowrap',
        fontFamily: k % 2 ? '"DM Serif Display", serif' : '"Anton", "Archivo Black", sans-serif', fontSize: `${size}px`, lineHeight: 1,
        color: '#141210', letterSpacing: k % 2 ? '0' : '.01em' });
      if (k % 4 === 1) Object.assign(row.style, { background: 'var(--accent)', padding: '0 24px', width: 'auto', left: `${30 + r() * 80}px` });
      const rule = el('div', '', page);
      Object.assign(rule.style, { position: 'absolute', left: '40px', right: '40px', top: `${y + size + 14}px`, height: '3px', background: '#141210' });
      rows.push({ row, rule, at: 0.03 * k, dir: k % 2 ? 1 : -1 });
      y += size + 40;
      k++;
    }
    return {
      seek(t) {
        page.style.opacity = fade(t, s.dur, 0.12);
        rows.forEach(({ row, rule, at, dir }) => {
          const p = ease.out(span(t, at, 0.35));
          row.style.transform = `translateX(${(1 - p) * dir * 300 + dir * t * 22}px)`;
          row.style.opacity = p;
          rule.style.transform = `scaleX(${p})`;
        });
      },
    };
  }

  // ---------------------------------------------------------------- Orbit: words circling the head (back half behind, front half in front)
  function orbit(s, root) {
    const f = faceOf(s);
    const cx = f.cx, cy = f.y0 + f.h * 0.12;
    const rx = Math.min(Math.max(f.w * 1.2, 300), cx - 150, W - cx - 150), ry = rx * 0.3;
    const words = s.data.texts.map((text) => {
      const n = el('div', 'pill orbit-word', root, text);
      Object.assign(n.style, { position: 'absolute', left: 0, top: 0, fontSize: '54px', whiteSpace: 'nowrap', transformOrigin: 'center' });
      return n;
    });
    const back = s.data.part === 'back';
    return {
      seek(t) {
        const a0 = t * 1.5;
        words.forEach((n, i) => {
          const a = a0 + (Math.PI * 2 * i) / words.length;
          const depth = Math.sin(a);  // > 0: the near side, in front of the head
          const visible = back ? depth <= 0 : depth > 0;
          const x = cx + rx * Math.cos(a), y = cy + ry * depth;
          const sc = 0.8 + 0.3 * (depth + 1) / 2;
          n.style.opacity = visible ? fade(t, s.dur) * (0.8 + 0.2 * (depth + 1) / 2) : 0;
          n.style.transform = `translate(${x - n.offsetWidth / 2}px, ${y - n.offsetHeight / 2}px) scale(${sc})`;
        });
      },
    };
  }

  // ---------------------------------------------------------------- Glass Type: words on a frosted panel (the blur is in the footage)
  function glassType(s, root) {
    const [x, y, w, h] = s.data.panel;
    const g = boxed(el('div', 'g glass-panel', root), [x, y, w, h]);
    Object.assign(g.style, { display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center' });
    const text = el('div', 'head glass-text', g, s.data.texts[0] || '');
    fitText(text, w * 0.86, h * 0.42, 18, { wrap: true, maxHeight: h * 0.78 });
    const shine = el('div', 'glass-shine', g);
    return {
      seek(t) {
        const p = ease.out(span(t, 0, 0.35));
        g.style.opacity = fade(t, s.dur, 0.2);
        g.style.transform = `translateY(${(1 - p) * 40}px) scale(${0.96 + 0.04 * p})`;
        text.style.letterSpacing = `${(1 - p) * 0.2}em`;
        shine.style.transform = `translateX(${-120 + 260 * ease.inOut(span(t, 0.2, 1.1))}%) skewX(-20deg)`;
      },
    };
  }

  // ---------------------------------------------------------------- Paper Cut: a torn paper label with tape
  function paperCut(s, root) {
    const [x, y, w, h] = s.data.panel;
    const r = rand(s.data.texts.join('|'));
    const g = boxed(el('div', 'g', root), [x + 40, y, w - 80, h]);
    const paper = el('div', 'paper-card', g);
    const pts = [];
    for (let i = 0; i <= 24; i++) pts.push(`${(i / 24) * 100}% ${r() * 5}%`);
    for (let i = 24; i >= 0; i--) pts.push(`${(i / 24) * 100}% ${95 + r() * 5}%`);
    paper.style.clipPath = `polygon(${pts.join(',')})`;
    const tape = el('div', 'paper-tape', g);
    const lines = s.data.texts.map((t) => el('div', 'paper-line', paper, t));
    lines.forEach((n) => fitText(n, (w - 80) * 0.84, (h * 0.72) / lines.length));
    const tilt = (r() - 0.5) * 5;
    return {
      seek(t) {
        const p = ease.back(span(t, 0, 0.4));
        g.style.opacity = fade(t, s.dur, 0.12);
        g.style.transform = `translateY(${(1 - p) * -80}px) rotate(${tilt + (1 - p) * 8}deg)`;
        tape.style.opacity = clamp(span(t, 0.25, 0.15));
      },
    };
  }

  // ---------------------------------------------------------------- Phone Mockup: the phone's body and app chrome (the screen is the footage)
  function phoneMockup(s, root) {
    const [x, y, w, h] = s.data.screen;
    const body = boxed(el('div', 'g phone-body', root), [x - 22, y - 22, w + 44, h + 44]);
    el('div', 'phone-island', body);
    const status = el('div', 'phone-status', body, '9:41');
    const text = s.data.texts[0] || '';
    const ui = el('div', `phone-ui phone-${s.data.choice}`, body);
    if (s.data.choice === 'chat') el('div', 'phone-bubble', ui, text || '…');
    else if (s.data.choice === 'search') { const bar = el('div', 'phone-search', ui); bar.dataset.text = text; }
    else if (s.data.choice === 'notes') { el('div', 'phone-notes-head', ui, 'Notes'); el('div', 'phone-notes', ui, text); }
    else { el('div', 'phone-feed-icons', ui, '♥  💬  ➤'); el('div', 'phone-caption', ui, text); }
    const bar = ui.querySelector('.phone-search');
    return {
      seek(t) {
        body.style.opacity = fade(t, s.dur, 0.12);
        ui.style.transform = `translateY(${(1 - ease.out(span(t, 0.15, 0.35))) * 60}px)`;
        ui.style.opacity = clamp(span(t, 0.15, 0.2));
        if (bar) bar.textContent = '🔍  ' + bar.dataset.text.slice(0, Math.round(bar.dataset.text.length * clamp(span(t, 0.3, 0.9))));
        status.style.opacity = 0.9;
      },
    };
  }

  // ---------------------------------------------------------------- Cover Story: a magazine cover, the title behind the head
  function coverStory(s, root) {
    const [title, ...lines] = s.data.texts;
    if (s.data.part === 'back') {
      const mast = el('div', 'cover-mast', root, (title || 'COVER').toUpperCase());
      Object.assign(mast.style, { position: 'absolute', left: '40px', top: '120px', width: `${W - 80}px`, textAlign: 'center' });
      fitText(mast, W - 80, 380);
      return { seek(t) { mast.style.opacity = fade(t, s.dur, 0.15); mast.style.transform = `scale(${1.08 - 0.08 * ease.out(span(t, 0, 0.5))})`; } };
    }
    const frame = full(root, 'cover-frame');
    const flash = full(root);
    flash.style.background = '#fff';
    const issue = el('div', 'cover-issue', frame, `ISSUE ${new Date().getFullYear()} · EXCLUSIVE`);
    const made = lines.map((text, i) => {
      const n = el('div', `cover-line ${i % 2 ? 'right' : 'left'}`, frame);
      el('span', 'cover-kicker', n, ['THE STORY', 'INSIDE', 'PLUS'][i] || 'MORE');
      el('div', 'cover-text', n, text);
      n.style.top = `${1180 + i * 190}px`;
      return n;
    });
    const code = el('div', 'cover-barcode', frame);
    return {
      seek(t) {
        flash.style.opacity = 1 - clamp(span(t, 0, 0.18));
        frame.style.opacity = fade(t, s.dur, 0.1);
        issue.style.opacity = clamp(span(t, 0.2, 0.2));
        made.forEach((n, i) => { const p = ease.out(span(t, 0.3 + i * 0.15, 0.35)); n.style.opacity = p; n.style.transform = `translateX(${(1 - p) * (i % 2 ? 60 : -60)}px)`; });
        code.style.opacity = clamp(span(t, 0.6, 0.2));
      },
    };
  }

  // ---------------------------------------------------------------- UI World: app cards floating around the speaker in perspective
  function uiWorld(s, root) {
    const f = faceOf(s);
    const spots = [[-1.25, -0.9], [1.2, -0.55], [-1.15, 0.75], [1.25, 0.95], [0, -1.6]];
    const back = s.data.part === 'back';
    const icons = ['🔔', '💬', '❤️', '💸', '📈'];
    const cards = s.data.texts.map((text, i) => {
      const behind = i % 3 === 1;  // every third card floats behind the head
      if (behind !== back) return null;
      const [dx, dy] = spots[i % spots.length];
      const card = el('div', 'ui-card', root);
      el('div', 'ui-icon', card, icons[i % icons.length]);
      el('div', 'ui-text', card, text);
      const x = Math.min(W - 520, Math.max(30, f.cx + dx * f.w * 1.1 - 240)), y = Math.min(H - 260, Math.max(200, f.cy + dy * f.h * 1.3));
      Object.assign(card.style, { position: 'absolute', left: `${x}px`, top: `${y}px` });
      return { card, at: 0.08 + i * 0.12, tilt: dx < 0 ? 16 : -16, bob: i * 1.7 };
    }).filter(Boolean);
    return {
      seek(t) {
        cards.forEach(({ card, at, tilt, bob }) => {
          const p = ease.back(span(t, at, 0.35));
          card.style.opacity = clamp(span(t, at, 0.15)) * fade(t, s.dur, 0.01);
          card.style.transform = `perspective(900px) rotateY(${tilt}deg) translateY(${Math.sin(t * 2.2 + bob) * 10}px) scale(${0.7 + 0.3 * p})`;
        });
      },
    };
  }

  // ---------------------------------------------------------------- Framebreak: the frame's label (the frame itself is in the footage)
  function framebreakLabel(s, root) {
    const cw = W * 0.8, ch = H * 0.8, ox = (W - cw) / 2, oy = (H - ch) / 2 + 60;
    const tag = el('div', 'pill framebreak-tag', root, (s.data.texts[0] || '').toUpperCase());
    Object.assign(tag.style, { position: 'absolute', left: `${ox + 30}px`, top: `${oy + ch - 120}px`, fontSize: '50px' });
    return { seek(t) { const p = ease.back(span(t, 0.15, 0.35)); tag.style.opacity = clamp(span(t, 0.15, 0.15)) * fade(t, s.dur, 0.01); tag.style.transform = `scale(${0.6 + 0.4 * p})`; } };
  }

  // ---------------------------------------------------------------- Green Screen: a world behind the speaker
  function greenScreen(s, root) {
    const bg = full(root, `world world-${s.data.choice}`);
    const r = rand(s.data.choice);
    const movers = [];
    const dots = (n, cls, size) => {
      for (let i = 0; i < n; i++) {
        const d = el('div', cls, bg);
        const sz = size[0] + r() * (size[1] - size[0]);
        Object.assign(d.style, { left: `${r() * 100}%`, top: `${r() * 100}%`, width: `${sz}px`, height: `${sz}px` });
        movers.push({ d, vx: (r() - 0.5) * 30, vy: (r() - 0.5) * 20, tw: r() * 6 });
      }
    };
    const choice = s.data.choice;
    if (choice === 'space') dots(80, 'star-dot', [2, 6]);
    if (choice === 'city') {
      for (let i = 0; i < 14; i++) {
        const b = el('div', 'city-block', bg);
        const w = 70 + r() * 90, h = 300 + r() * 700;
        Object.assign(b.style, { left: `${(i / 14) * 100 - 3}%`, width: `${w}px`, height: `${h}px` });
      }
      dots(28, 'bokeh', [30, 90]);
    }
    if (choice === 'brand' || choice === 'studio') dots(6, 'soft-blob', [300, 600]);
    if (choice === 'stage') { el('div', 'stage-light', bg); el('div', 'curtain left', bg); el('div', 'curtain right', bg); }
    if (choice === 'nature') { el('div', 'sun', bg); el('div', 'hill far', bg); el('div', 'hill near', bg); }
    if (choice === 'neon') { el('div', 'neon-grid', bg); el('div', 'neon-horizon', bg); }
    const grid = bg.querySelector('.neon-grid');
    return {
      seek(t) {
        bg.style.opacity = fade(t, s.dur, 0.12);
        movers.forEach(({ d, vx, vy, tw }) => {
          d.style.transform = `translate(${vx * t}px, ${vy * t}px)`;
          if (choice === 'space') d.style.opacity = 0.5 + 0.5 * Math.sin(t * 3 + tw);
        });
        if (grid) grid.style.backgroundPositionY = `${t * 180}px`;
      },
    };
  }

  // ---------------------------------------------------------------- Couch Wall: the speaker in front of a wall covered in one phrase
  function couchWall(s, root) {
    const bg = full(root, 'couch-wall');
    const phrase = (s.data.texts[0] || '').toUpperCase();
    const rows = [];
    for (let k = 0; k < 11; k++) {
      const row = el('div', `wall-row ${k % 2 ? 'outline' : ''}`, bg, Array(8).fill(phrase).join('  •  '));
      row.style.top = `${k * 180 - 40}px`;
      rows.push({ row, dir: k % 2 ? 1 : -1, off: (k * 137) % 400 });
    }
    return {
      seek(t) {
        bg.style.opacity = fade(t, s.dur, 0.12);
        rows.forEach(({ row, dir, off }) => { row.style.transform = `translateX(${-off + dir * t * 60}px)`; });
      },
    };
  }

  const LOOKS = {
    doodle, headline_wall: headlineWall, orbit, glass_type: glassType, paper_cut: paperCut, phone_mockup: phoneMockup,
    cover_story: coverStory, ui_world: uiWorld, framebreak: framebreakLabel, green_screen: greenScreen, couch_wall: couchWall,
  };

  T.effect = (s, root) => {
    const look = LOOKS[s.data.effect];
    if (!look) throw new Error(`No look for effect ${s.data.effect}`);
    return look(s, root);
  };
})();
