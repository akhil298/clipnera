// Graphic beat templates. Beats.mount(spec) builds one beat; Beats.seek(t) poses it at t seconds.
// Everything is a pure function of t, so every frame renders the same way every time.
(() => {
  const stage = document.getElementById('stage');
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const ease = {
    out: t => 1 - Math.pow(1 - t, 3),
    expo: t => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    back: t => { const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
    inOut: t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  };
  const span = (t, start, length) => clamp((t - start) / length);
  const ENTER = 0.3, EXIT = 0.22;

  function el(tag, cls, parent, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }
  function boxed(node, [x, y, w, h]) {
    Object.assign(node.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
    return node;
  }
  function fitText(node, maxWidth, maxSize, minSize = 18) {
    let size = maxSize;
    node.style.fontSize = `${size}px`;
    while (size > minSize && node.scrollWidth > maxWidth) {
      size *= 0.94;
      node.style.fontSize = `${size}px`;
    }
    return size;
  }
  // Fade and settle in, fade and shrink out: the one envelope every beat shares.
  function envelope(node, t, dur, { from = 0.86, blur = 10, rise = 26 } = {}) {
    const a = ease.back(span(t, 0, ENTER)), z = 1 - ease.out(span(t, dur - EXIT, EXIT));
    const scale = (from + (1 - from) * a) * (0.96 + 0.04 * z);
    node.style.opacity = clamp(span(t, 0, ENTER * 0.6) * z);
    node.style.transform = `translateY(${(1 - a) * rise}px) scale(${scale})`;
    node.style.filter = blur ? `blur(${(1 - clamp(a)) * blur}px)` : '';
  }
  function reveal(node, t, at, { dx = 0, dy = 22, from = 0.7 } = {}) {
    const p = ease.back(span(t, at, 0.32));
    node.style.opacity = clamp(span(t, at, 0.18));
    node.style.transform = `translate(${(1 - p) * dx}px, ${(1 - p) * dy}px) scale(${from + (1 - from) * p})`;
  }
  function rng(seed) {
    let s = [...String(seed)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 2166136261);
    return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  }
  const markGlyph = { check: '✓', cross: '✕', none: '' };

  /* ---------- templates: each returns { seek(t) } ---------- */
  const T = {};
  // Extra template files (footage.js) add their templates through these hooks.
  window.BeatsKit = { T, el, boxed, fitText, envelope, reveal, ease, span, clamp, EXIT };

  T.count_up = (s, root) => {
    const { prefix = '', number = '0', suffix = '', label = '' } = s.data;
    const target = parseFloat(String(number).replace(/,/g, '')) || 0;
    const decimals = (String(number).split('.')[1] || '').length;
    const grouped = String(number).includes(',');
    const indian = /\d,\d\d,\d{3}/.test(number);
    const fmt = v => (grouped
      ? v.toLocaleString(indian ? 'en-IN' : 'en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
      : v.toFixed(decimals));
    const card = s.place === 'card';
    if (card) el('div', 'full page', root);
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '0.2em' });
    const fig = el('div', `figure ${s.place === 'behind' ? 'behind-text' : card ? 'accent' : 'glow'}`, g);
    fig.style.color = s.place === 'beside' ? '#fff' : '';
    fig.textContent = `${prefix}${fmt(target)}${suffix}`;
    const size = fitText(fig, s.box[2] * 0.96, s.box[3] * (label ? 0.7 : 0.9));
    let lab = null;
    if (label) {
      lab = el('div', card ? 'head soft' : 'pill', g, label);
      lab.style.fontSize = `${Math.max(26, size * 0.2)}px`;
    }
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.6, blur: 14 });
        const v = target * ease.expo(span(t, 0.08, 0.9));
        fig.textContent = `${prefix}${fmt(decimals ? v : Math.round(v))}${suffix}`;
        if (lab) reveal(lab, t, 0.45);
      },
    };
  };

  function rows(s, root, { numbered = false } = {}) {
    const items = s.data.items || [], title = s.data.title || '';
    const card = boxed(el('div', 'g card', root), s.box);
    const pad = Math.round(s.box[2] * 0.06);
    Object.assign(card.style, { padding: `${pad}px`, display: 'flex', flexDirection: 'column', gap: `${pad * 0.45}px`, justifyContent: 'center' });
    const rowH = Math.min((s.box[3] - pad * 2) / (items.length + (title ? 1.3 : 0.2)), s.box[2] * 0.15);
    let head = null;
    if (title) {
      head = el('div', 'head accent', card, title.toUpperCase());
      head.style.fontSize = `${rowH * 0.42}px`;
      head.style.letterSpacing = '0.08em';
    }
    const made = items.map((text, i) => {
      const row = el('div', 'chip', card);
      row.style.fontSize = `${rowH * 0.42}px`;
      const mark = el('div', `mark ${s.data.mark || 'none'}`, row, numbered || s.data.mark === 'none' ? String(i + 1) : markGlyph[s.data.mark]);
      el('div', '', row, text);
      return { row, mark };
    });
    return { card, head, made };
  }

  T.list = (s, root) => {
    const { card, head, made } = rows(s, root);
    const steps = s.steps.length === made.length ? s.steps : made.map((_, i) => 0.2 + i * 0.45);
    return {
      seek(t) {
        envelope(card, t, s.dur);
        if (head) reveal(head, t, 0.05, { dy: 10 });
        made.forEach(({ row, mark }, i) => {
          reveal(row, t, steps[i], { dx: -40, dy: 0, from: 0.9 });
          const p = ease.back(span(t, steps[i] + 0.08, 0.3));
          mark.style.transform = `scale(${p})`;
        });
      },
    };
  };

  T.flow = (s, root) => {
    const items = s.data.items || [];
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'space-evenly' });
    const nodeH = Math.min(s.box[3] / (items.length * 1.6), s.box[2] * 0.16);
    const parts = items.map((text, i) => {
      const node = el('div', 'pill', g, text);
      node.style.fontSize = `${nodeH * 0.42}px`;
      let link = null;
      if (i < items.length - 1) {
        link = el('div', '', g);
        Object.assign(link.style, { width: '6px', height: `${nodeH * 0.5}px`, borderRadius: '3px', background: 'var(--accent)', transformOrigin: 'top' });
      }
      return { node, link };
    });
    const steps = s.steps.length === items.length ? s.steps : items.map((_, i) => 0.2 + i * 0.5);
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.95, blur: 0, rise: 0 });
        parts.forEach(({ node, link }, i) => {
          reveal(node, t, steps[i]);
          if (link) link.style.transform = `scaleY(${ease.inOut(span(t, steps[i] + 0.15, Math.max(0.2, (steps[i + 1] ?? steps[i] + 0.5) - steps[i] - 0.15)))})`;
        });
      },
    };
  };

  T.logo = (s, root) => {
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5em' });
    const side = Math.min(s.box[3], s.box[2] * 0.42);
    const tile = el('div', 'card', g);
    Object.assign(tile.style, { width: `${side}px`, height: `${side}px`, display: 'grid', placeItems: 'center', background: '#fff', borderRadius: `${side * 0.24}px` });
    if (s.asset) {
      const img = el('img', '', tile);
      img.src = s.asset;
      Object.assign(img.style, { width: '64%', height: '64%', objectFit: 'contain' });
    }
    const name = el('div', 'pill', g, s.data.text || '');
    name.style.fontSize = `${side * 0.2}px`;
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.4, blur: 8 });
        tile.style.transform = `rotate(${(1 - ease.back(span(t, 0, 0.4))) * -12}deg)`;
        reveal(name, t, 0.18, { dx: -30, dy: 0 });
      },
    };
  };

  T.name = (s, root) => {
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', alignItems: 'center', justifyContent: 'center' });
    const tag = el('div', 'card', g);
    Object.assign(tag.style, { display: 'flex', alignItems: 'stretch', overflow: 'hidden', borderRadius: '20px' });
    const bar = el('div', '', tag);
    Object.assign(bar.style, { width: '14px', background: 'var(--accent)' });
    const text = el('div', '', tag);
    Object.assign(text.style, { padding: '0.45em 0.9em', display: 'flex', flexDirection: 'column' });
    const main = el('div', 'head', text, s.data.text || '');
    main.style.fontWeight = 800;
    fitText(main, s.box[2] * 0.8, s.box[3] * 0.42);
    if (s.data.label) {
      const sub = el('div', 'soft', text, s.data.label);
      sub.style.fontSize = `${parseFloat(main.style.fontSize) * 0.5}px`;
    }
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.9, blur: 6, rise: 0 });
        const p = ease.out(span(t, 0, 0.35));
        tag.style.clipPath = `inset(0 ${(1 - p) * 100}% 0 0 round 20px)`;
      },
    };
  };

  T.keyword = (s, root) => {
    const behind = s.place === 'behind';
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' });
    let lead = null;
    if (s.data.lead) {
      lead = el('div', behind ? 'head' : 'head glow', g, s.data.lead);
      lead.style.color = behind ? 'var(--ink)' : '#fff';
      lead.style.fontSize = `${s.box[3] * (behind ? 0.1 : 0.2)}px`;
    }
    // A narrow band (beside the speaker) stacks the words, one per line, so each stays big.
    const text = behind ? s.data.text.toUpperCase() : s.data.text;
    const stacked = s.box[2] < s.W * 0.5 && text.includes(' ');
    const lines = stacked ? text.split(/\s+/) : [text];
    const room = s.box[3] * (behind ? 0.9 : 0.8) / lines.length;
    const chars = [];
    lines.forEach(line => {
      const word = el('div', `figure ${behind ? '' : 'accent glow'}`, g);
      // The gradient fill goes on each letter: background-clip:text does not reach inline-block children.
      [...line].forEach(c => {
        const ch = el('span', behind ? 'behind-text' : '', word, c === ' ' ? '\u00a0' : c);
        ch.style.display = 'inline-block';
        chars.push(ch);
      });
      fitText(word, s.box[2] * 0.98, room);
    });
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: behind ? 1.12 : 0.7, blur: behind ? 0 : 10, rise: 0 });
        if (lead) reveal(lead, t, 0, { dy: 12 });
        chars.forEach((ch, i) => {
          const p = ease.back(span(t, 0.03 + i * 0.03, 0.3));
          ch.style.transform = `translateY(${(1 - p) * 60}%)`;
          ch.style.opacity = clamp(span(t, 0.03 + i * 0.03, 0.15));
        });
      },
    };
  };

  T.statement = (s, root) => {
    const page = el('div', 'full page', root);
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '0.4em', textAlign: 'center' });
    let label = null;
    if (s.data.label) {
      label = el('div', 'head accent', g, s.data.label.toUpperCase());
      label.style.fontSize = `${s.box[2] * 0.045}px`;
      label.style.letterSpacing = '0.12em';
    }
    const text = el('div', 'head', g);
    Object.assign(text.style, { fontWeight: 800, lineHeight: 1.08, fontSize: `${s.box[2] * 0.12}px` });
    const words = s.data.text.split(/\s+/).map((w, i, all) => {
      const node = el('span', i === all.length - 1 ? 'accent' : '', text, w);
      node.style.display = 'inline-block';
      node.style.margin = '0 0.14em';
      return node;
    });
    while (text.scrollHeight > s.box[3] * 0.8 && parseFloat(text.style.fontSize) > 30) {
      text.style.fontSize = `${parseFloat(text.style.fontSize) * 0.92}px`;
    }
    return {
      seek(t) {
        const z = 1 - ease.out(span(t, s.dur - EXIT, EXIT));
        page.style.opacity = clamp(span(t, 0, 0.18)) * z;
        g.style.opacity = z;
        if (label) reveal(label, t, 0.05, { dy: 14 });
        words.forEach((w, i) => reveal(w, t, 0.1 + i * 0.09, { dy: 34, from: 0.8 }));
      },
    };
  };

  T.object = (s, root) => {
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' });
    const side = Math.min(s.box[2], s.box[3] * (s.data.text ? 0.78 : 0.95));
    const img = el('img', 'lift', g);
    img.src = s.asset;
    Object.assign(img.style, { width: `${side}px`, height: `${side}px`, objectFit: 'contain' });
    let cap = null;
    if (s.data.text) {
      cap = el('div', 'pill', g, s.data.text);
      cap.style.fontSize = `${side * 0.12}px`;
    }
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.2, blur: 6, rise: 40 });
        img.style.transform = `translateY(${Math.sin(t * 2.6) * 8}px) rotate(${Math.sin(t * 1.7) * 3}deg)`;
        if (cap) reveal(cap, t, 0.25);
      },
    };
  };

  T.chart = (s, root) => {
    const card = boxed(el('div', 'g card', root), s.box);
    const pad = s.box[2] * 0.07;
    Object.assign(card.style, { padding: `${pad}px`, display: 'flex', flexDirection: 'column', gap: `${pad * 0.4}px` });
    const up = s.data.trend !== 'down';
    if (s.data.label) {
      const head = el('div', 'head', card, s.data.label);
      Object.assign(head.style, { fontWeight: 800, fontSize: `${s.box[2] * 0.075}px` });
    }
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 100 60');
    Object.assign(svg.style, { width: '100%', flex: '1' });
    card.appendChild(svg);
    const r = rng(s.id), n = 7;
    const ys = Array.from({ length: n }, (_, i) => {
      const trend = up ? 52 - (i / (n - 1)) * 42 : 10 + (i / (n - 1)) * 42;
      return clamp(trend + (r() - 0.5) * 10, 4, 56);
    });
    const pts = ys.map((y, i) => [4 + (i / (n - 1)) * 92, y]);
    const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    const colour = up ? 'var(--good)' : 'var(--bad)';
    for (let i = 1; i < 4; i++) {
      const grid = document.createElementNS(ns, 'line');
      Object.entries({ x1: 0, x2: 100, y1: i * 15, y2: i * 15, stroke: 'currentColor', 'stroke-opacity': 0.1, 'stroke-width': 0.4 }).forEach(([k, v]) => grid.setAttribute(k, v));
      svg.appendChild(grid);
    }
    const area = document.createElementNS(ns, 'path');
    area.setAttribute('d', `${d} L96,60 L4,60 Z`);
    area.setAttribute('fill', colour);
    area.setAttribute('fill-opacity', 0.14);
    svg.appendChild(area);
    const line = document.createElementNS(ns, 'path');
    Object.entries({ d, fill: 'none', stroke: colour, 'stroke-width': 2.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }).forEach(([k, v]) => line.setAttribute(k, v));
    svg.appendChild(line);
    const dot = document.createElementNS(ns, 'circle');
    Object.entries({ r: 2.6, fill: colour, cx: pts[n - 1][0], cy: pts[n - 1][1] }).forEach(([k, v]) => dot.setAttribute(k, v));
    svg.appendChild(dot);
    const length = line.getTotalLength();
    line.style.strokeDasharray = length;
    let tag = null;
    if ((s.data.figures || []).length) {
      tag = el('div', 'pill', card, `${up ? '▲' : '▼'} ${s.data.figures.at(-1)}`);
      Object.assign(tag.style, { alignSelf: 'flex-end', color: up ? 'var(--good)' : 'var(--bad)', fontSize: `${s.box[2] * 0.06}px` });
    }
    return {
      seek(t) {
        envelope(card, t, s.dur);
        const p = ease.inOut(span(t, 0.2, 1.2));
        line.style.strokeDashoffset = length * (1 - p);
        area.style.clipPath = `inset(0 ${(1 - p) * 100}% 0 0)`;
        dot.setAttribute('r', 2.6 * ease.back(span(t, 1.3, 0.3)) * (1 + 0.15 * Math.sin(t * 8)));
        if (tag) reveal(tag, t, 1.35);
      },
    };
  };

  T.ui = (s, root) => {
    const g = boxed(el('div', 'g', root), s.box);
    const v = s.data.variant;
    const fs = s.box[2] * 0.052;
    Object.assign(g.style, { display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: `${fs * 0.7}px`, fontSize: `${fs}px` });
    const items = s.data.items || [];
    const steps = s.steps.length === items.length ? s.steps : items.map((_, i) => 0.3 + i * 0.55);
    if (v === 'search') {
      const bar = el('div', 'ui-bar', g);
      el('div', '', bar, '🔍');
      const typed = el('div', '', bar);
      const cursor = el('div', '', bar, '|');
      const query = s.data.text || items.join(' ');
      return {
        seek(t) {
          envelope(g, t, s.dur);
          const shown = Math.floor(clamp((t - 0.35) * 22, 0, query.length));
          typed.textContent = query.slice(0, shown);
          cursor.style.opacity = shown < query.length || Math.floor(t * 2.4) % 2 ? 1 : 0;
        },
      };
    }
    if (v === 'chat') {
      Object.assign(g.style, { alignItems: 'stretch' });
      const lines = items.length ? items : [s.data.text];
      const bubbles = lines.map((text, i) => el('div', `bubble ${i % 2 ? 'them' : 'me'}`, g, text));
      return { seek(t) { envelope(g, t, s.dur, { from: 0.95, blur: 0 }); bubbles.forEach((b, i) => reveal(b, t, steps[i] ?? 0.2 + i * 0.5, { dy: 30 })); } };
    }
    if (v === 'checklist') {
      g.remove();
      const { card, made } = rows({ ...s, data: { title: s.data.text, items, mark: 'check' } }, root);
      return {
        seek(t) {
          envelope(card, t, s.dur);
          made.forEach(({ row, mark }, i) => { reveal(row, t, steps[i], { dx: -30, dy: 0 }); mark.style.transform = `scale(${ease.back(span(t, steps[i] + 0.15, 0.3))})`; });
        },
      };
    }
    const lines = items.length ? items : [s.data.text];
    const cards = lines.map(text => {
      const card = el('div', 'notif', g);
      el('div', 'dot', card);
      el('div', '', card, text);
      return card;
    });
    return { seek(t) { envelope(g, t, s.dur, { from: 0.98, blur: 0 }); cards.forEach((c, i) => reveal(c, t, steps[i] ?? 0.2 + i * 0.5, { dy: -50, from: 0.9 })); } };
  };

  T.image = (s, root) => {
    const frame = el('div', 'full', root);
    frame.style.overflow = 'hidden';
    const img = el('img', 'full', frame);
    img.src = s.asset;
    Object.assign(img.style, { width: '100%', height: '100%', objectFit: 'cover' });
    const shade = el('div', 'full', frame);
    shade.style.background = 'linear-gradient(180deg, rgba(0,0,0,.25) 0%, transparent 30%, transparent 55%, rgba(0,0,0,.65) 100%)';
    let cap = null;
    if (s.data.text) {
      cap = boxed(el('div', 'g head', root), s.box);
      Object.assign(cap.style, { color: '#fff', fontWeight: 800, textAlign: 'center', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', lineHeight: 1.1 });
      cap.textContent = s.data.text;
      cap.style.fontSize = `${s.box[2] * 0.085}px`;
      cap.style.textShadow = '0 6px 24px rgba(0,0,0,.6)';
    }
    const r = rng(s.id), dx = (r() - 0.5) * 4, dy = (r() - 0.5) * 4;
    return {
      seek(t) {
        const z = 1 - ease.out(span(t, s.dur - EXIT, EXIT));
        frame.style.opacity = clamp(span(t, 0, 0.22)) * z;
        const p = t / Math.max(s.dur, 0.1);
        img.style.transform = `scale(${1.05 + 0.08 * p}) translate(${dx * p}%, ${dy * p}%)`;
        if (cap) { reveal(cap, t, 0.2); cap.style.opacity = Number(cap.style.opacity) * z; }
      },
    };
  };

  T.cta = (s, root) => {
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', alignItems: 'center', justifyContent: 'center' });
    const pill = el('div', 'pill', g);
    pill.style.fontSize = `${s.box[3] * 0.32}px`;
    pill.style.background = 'var(--accent)';
    pill.style.color = 'var(--accent-ink)';
    el('span', '', pill, s.data.verb || 'COMMENT');
    if (s.data.text) el('span', '', pill, `“${s.data.text}”`);
    fitText(pill, s.box[2] * 0.95, s.box[3] * 0.32);
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.3, blur: 0 });
        pill.style.transform = `scale(${1 + 0.05 * Math.max(0, Math.sin((t - 0.5) * 6))})`;
      },
    };
  };

  T.map = (s, root) => {
    const card = boxed(el('div', 'g card', root), s.box);
    const pad = s.box[2] * 0.06;
    Object.assign(card.style, { padding: `${pad}px`, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: `${pad * 0.4}px`, overflow: 'hidden' });
    const holder = el('div', '', card);
    Object.assign(holder.style, { width: '100%', flex: '1 1 0', minHeight: 0, position: 'relative' });
    holder.innerHTML = s.data.svg || '';
    const svg = holder.querySelector('svg');
    const paths = svg ? [...svg.querySelectorAll('path')] : [];
    if (svg) {
      svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      Object.assign(svg.style, { position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' });
    }
    const lengths = paths.map(p => {
      Object.entries({ fill: 'var(--accent)', 'fill-opacity': 0, stroke: 'var(--ink)', 'stroke-width': 1.5, 'vector-effect': 'non-scaling-stroke' }).forEach(([k, v]) => p.setAttribute(k, v));
      const length = p.getTotalLength();
      p.style.strokeDasharray = length;
      return length;
    });
    const label = el('div', 'pill', card, `📍 ${s.data.text}`);
    label.style.fontSize = `${s.box[2] * 0.06}px`;
    return {
      seek(t) {
        envelope(card, t, s.dur);
        const p = ease.inOut(span(t, 0.15, 1.0));
        paths.forEach((path, i) => {
          path.style.strokeDashoffset = lengths[i] * (1 - p);
          path.setAttribute('fill-opacity', 0.35 * ease.out(span(t, 1.0, 0.4)));
        });
        reveal(label, t, 1.0);
      },
    };
  };

  let current = null;
  window.Beats = {
    ready: true,
    mount(spec) {
      stage.innerHTML = '';
      stage.className = `theme-${spec.theme || 'clean'}`;
      if (spec.accent) stage.style.setProperty('--accent', spec.accent);
      const make = T[spec.kind];
      if (!make) throw new Error(`No template for ${spec.kind}`);
      current = make({ steps: [], data: {}, ...spec }, stage);
      current.seek(0);
      return true;
    },
    seek(t) { current.seek(t); return true; },
  };
})();
