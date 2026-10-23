// Templates for the reel engine's footage edits, styled after the Before/After reels:
// chapter cards, 2-tier labels, ingredient tags, a flicker word montage, a step progress bar, colour washes.
(() => {
  const { T, el, boxed, fitText, envelope, reveal, ease, span, clamp } = window.BeatsKit;

  function letters(parent, text, cls) {
    const word = el('div', cls, parent);
    const chars = [...text].map(c => {
      const ch = el('span', '', word, c === ' ' ? ' ' : c);
      ch.style.display = 'inline-block';
      return ch;
    });
    return { word, chars };
  }
  function rise(chars, t, at, gap = 0.028) {
    chars.forEach((ch, i) => {
      const p = ease.back(span(t, at + i * gap, 0.3));
      ch.style.transform = `translateY(${(1 - p) * 70}%) rotate(${(1 - p) * 8}deg)`;
      ch.style.opacity = clamp(span(t, at + i * gap, 0.12));
    });
  }
  function shade(root, top, height, dur) {
    const band = el('div', 'full', root);
    band.style.background = `linear-gradient(180deg, transparent ${top}%, rgba(10,6,0,.55) ${top + height * 0.35}%, rgba(10,6,0,.55) ${top + height * 0.65}%, transparent ${top + height}%)`;
    return t => { band.style.opacity = clamp(span(t, 0, 0.2)) * (1 - ease.out(span(t, dur - 0.22, 0.22))); };
  }

  // Step card: giant faded number, floating 3D icon, small lead + big keyword.
  T.chapter = (s, root) => {
    const [x, y, w, h] = s.box;
    const fade = shade(root, (y / s.H) * 100 - 6, (h / s.H) * 100 + 12, s.dur);
    const num = boxed(el('div', 'g figure', root, s.data.num), [x - w * 0.04, y - h * 0.18, w, h * 1.3]);
    Object.assign(num.style, { fontSize: `${h * 1.25}px`, color: 'transparent', WebkitTextStroke: '3px rgba(255,255,255,.35)', lineHeight: 1 });
    const side = s.asset ? h * 0.7 : 0;
    let icon = null;
    if (s.asset) {
      icon = el('img', 'g lift', root);
      icon.src = s.asset;
      boxed(icon, [x + w - side, y + (h - side) / 2, side, side]);
    }
    const text = boxed(el('div', 'g', root), [x + w * 0.02, y + h * 0.12, w - side - w * 0.04, h * 0.8]);
    Object.assign(text.style, { display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '0.1em' });
    const lead = el('div', 'head lead lead-caps', text, s.data.lead);
    lead.style.fontSize = `${h * 0.17}px`;
    const big = letters(text, s.data.text, 'figure key');
    big.word.style.alignSelf = 'flex-start';
    fitText(big.word, w - side - w * 0.06, h * 0.56);
    return {
      seek(t) {
        fade(t);
        const out = 1 - ease.out(span(t, s.dur - 0.22, 0.22));
        const p = ease.expo(span(t, 0, 0.5));
        num.style.opacity = 0.9 * p * out;
        num.style.transform = `translateX(${(1 - p) * -120}px)`;
        num.style.filter = `blur(${(1 - p) * 12}px)`;
        const q = ease.back(span(t, 0.12, 0.4));
        if (icon) icon.style.opacity = clamp(span(t, 0.12, 0.15)) * out;
        if (icon) icon.style.transform = `scale(${0.2 + 0.8 * q}) rotate(${(1 - q) * -25 + Math.sin(t * 3) * 4}deg) translateY(${Math.sin(t * 2.4) * 10}px)`;
        reveal(lead, t, 0.08, { dy: 16 });
        lead.style.opacity = Number(lead.style.opacity) * out;
        rise(big.chars, t, 0.16);
        text.style.opacity = out;
      },
    };
  };

  // Small lead + big keyword (2-tier caption), optional 3D icon to its left.
  T.two = (s, root) => {
    const [x, y, w, h] = s.box;
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: `${h * 0.08}px` });
    let icon = null;
    if (s.asset) {
      icon = el('img', 'lift', g);
      icon.src = s.asset;
      Object.assign(icon.style, { width: `${h * 0.6}px`, height: `${h * 0.6}px`, objectFit: 'contain', flex: 'none' });
    }
    const col = el('div', '', g);
    Object.assign(col.style, { display: 'flex', flexDirection: 'column', alignItems: icon ? 'flex-start' : 'center' });
    let lead = null;
    if (s.data.lead) {
      lead = el('div', 'head lead', col, s.data.lead);
      lead.style.fontSize = `${h * 0.22}px`;
    }
    const big = letters(col, s.data.text, `figure key${s.data.alt ? ' alt' : ''}`);
    fitText(big.word, w - (icon ? h : 0) - 20, h * (lead ? 0.62 : 0.85));
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.9, blur: 6, rise: 12 });
        if (lead) reveal(lead, t, 0, { dy: 14 });
        rise(big.chars, t, 0.06);
        if (icon) icon.style.transform = `scale(${ease.back(span(t, 0.05, 0.35))}) rotate(${Math.sin(t * 2.6) * 5}deg)`;
      },
    };
  };

  // Caption line: the words in the order they are said, each popping in on its word, the keyword bigger in the
  // style's accent (2-tier), an optional icon before it.
  T.caption = (s, root) => {
    const [x, y, w, h] = s.box;
    const g = boxed(el('div', 'g caption', root), s.box);
    Object.assign(g.style, { display: 'flex', flexWrap: 'wrap', alignItems: 'center', alignContent: 'center', justifyContent: 'center',
      columnGap: `${h * 0.07}px`, rowGap: `${h * 0.02}px`, textAlign: 'center' });
    let icon = null;
    if (s.asset) {
      icon = el('img', 'lift', g);
      icon.src = s.asset;
      Object.assign(icon.style, { width: `${h * 0.42}px`, height: `${h * 0.42}px`, objectFit: 'contain' });
    }
    // look: how this line moves - pop (words rise in), stack (the big word on its own line), slide (words glide in
    // from the left), punch (the line lands at once and the big word slams in over an accent bar).
    const look = s.data.look || 'pop';
    const words = (s.data.words || []).map((wd) => {
      const node = el('span', wd.key ? `figure key look-${look}${s.data.alt ? ' alt' : ''}` : 'head lead', g, wd.text);
      node.style.display = 'inline-block';
      node.style.fontSize = `${h * (wd.key ? (look === 'stack' ? 0.56 : 0.44) : 0.26)}px`;
      node.style.lineHeight = '1.05';
      let bar = null;
      if (wd.key && look === 'stack') node.style.flexBasis = '100%';
      if (wd.key && look === 'punch') {
        node.style.position = 'relative';
        bar = el('span', 'key-bar', node);
      }
      return { node, bar, key: !!wd.key, at: look === 'punch' ? Math.min(wd.at || 0, 0.12) : wd.at || 0 };
    });
    let scale = 1;
    while ((g.scrollHeight > h * 1.02 || g.scrollWidth > w * 1.02) && scale > 0.45) {
      scale *= 0.92;
      words.forEach(({ node }) => { node.style.fontSize = `${parseFloat(node.style.fontSize) * 0.92}px`; });
    }
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.96, blur: 0, rise: 8 });
        words.forEach(({ node, bar, key, at }) => {
          const p = ease.back(span(t, at, 0.22));
          node.style.opacity = clamp(span(t, at, 0.1));
          if (look === 'slide') {
            const q = ease.out(span(t, at, 0.28));
            node.style.transform = `translateX(${(1 - q) * -60}px)`;
            node.style.filter = `blur(${(1 - q) * 6}px)`;
          } else if (look === 'punch' && key) {
            const q = ease.back(span(t, at + 0.08, 0.3));
            node.style.transform = `scale(${1.7 - 0.7 * q})`;
            if (bar) bar.style.transform = `scaleX(${ease.out(span(t, at + 0.2, 0.35))})`;
          } else if (look === 'punch') {
            node.style.transform = '';
          } else {
            node.style.transform = `translateY(${(1 - p) * 30}%) scale(${(look === 'stack' && key ? 0.6 : 0.85) + (look === 'stack' && key ? 0.4 : 0.15) * p})`;
          }
        });
        if (icon) icon.style.transform = `scale(${ease.back(span(t, 0.05, 0.3))})`;
      },
    };
  };

  // Ingredient tag: a pill with a 3D icon, popped beside the thing it names.
  T.tag = (s, root) => {
    const [x, y, w, h] = s.box;
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'flex', alignItems: 'center', justifyContent: s.data.align || 'flex-start' });
    const pill = el('div', 'pill tag-pill', g);
    Object.assign(pill.style, { fontSize: `${h * 0.36}px`, padding: '0.25em 0.8em 0.25em 0.3em' });
    let img = null;
    if (s.asset) {
      img = el('img', '', pill);
      img.src = s.asset;
      Object.assign(img.style, { width: `${h * 0.8}px`, height: `${h * 0.8}px`, objectFit: 'contain' });
    } else {
      pill.style.paddingLeft = '0.8em';
    }
    el('span', '', pill, s.data.text);
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.3, blur: 0, rise: 30 });
        if (img) img.style.transform = `rotate(${(1 - ease.back(span(t, 0, 0.45))) * -40 + Math.sin(t * 3) * 6}deg)`;
      },
    };
  };

  // Flicker montage: one slammed word per shot, hard cuts between them.
  T.flicker = (s, root) => {
    const g = boxed(el('div', 'g', root), s.box);
    Object.assign(g.style, { display: 'grid', placeItems: 'center' });
    const words = s.data.items.map(item => {
      const word = el('div', 'figure flick', g, item.text);
      word.style.gridArea = '1 / 1';
      fitText(word, s.box[2] * 0.95, s.box[3]);
      return word;
    });
    return {
      seek(t) {
        const at = s.data.items.map(i => i.at);
        let n = at.findIndex((a, i) => t >= a && t < (at[i + 1] ?? s.dur));
        words.forEach((w, i) => {
          const on = i === n, p = on ? ease.out(span(t, at[i], 0.12)) : 0;
          w.style.opacity = on ? 1 : 0;
          w.style.transform = `scale(${1.35 - 0.35 * p})`;
        });
      },
    };
  };

  // Step progress bar along the top: a dot per step, the fill runs to the current step.
  T.progress = (s, root) => {
    const [x, y, w, h] = s.box;
    const g = boxed(el('div', 'g', root), s.box);
    const track = el('div', '', g);
    Object.assign(track.style, { position: 'absolute', left: '0', right: '0', top: `${h * 0.3}px`, height: `${h * 0.12}px`, borderRadius: '99px', background: 'rgba(255,255,255,.35)' });
    const fill = el('div', '', track);
    Object.assign(fill.style, { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: '99px', background: 'var(--accent)', boxShadow: '0 0 16px rgba(255,176,32,.9)' });
    const n = s.data.steps.length;
    const dots = s.data.steps.map((label, i) => {
      const cx = (w * i) / (n - 1);
      const dot = el('div', '', g);
      Object.assign(dot.style, { position: 'absolute', left: `${cx - h * 0.18}px`, top: `${h * 0.18}px`, width: `${h * 0.36}px`, height: `${h * 0.36}px`, borderRadius: '50%', background: '#fff', boxShadow: '0 2px 8px rgba(0,0,0,.4)' });
      const lab = el('div', 'head', g, label);
      Object.assign(lab.style, { position: 'absolute', top: `${h * 0.6}px`, left: `${cx}px`, transform: 'translateX(-50%)', color: '#fff', fontWeight: 800, fontSize: '30px', whiteSpace: 'nowrap', textShadow: '0 2px 10px rgba(0,0,0,.7)' });
      if (i === 0) lab.style.transform = 'translateX(-15%)';
      if (i === n - 1) lab.style.transform = 'translateX(-85%)';
      return { dot, lab };
    });
    const at = s.data.at;
    return {
      seek(t) {
        g.style.opacity = clamp(span(t, 0, 0.3)) * (1 - span(t, s.dur - 0.3, 0.3));
        let reached = 0;
        at.forEach((a, i) => { if (t >= a) reached = i; });
        const next = at[reached + 1] ?? s.dur;
        const within = clamp((t - at[reached]) / Math.max(0.1, next - at[reached]));
        fill.style.width = `${Math.min(100, ((reached + within * (reached < n - 1 ? 1 : 0)) / (n - 1)) * 100)}%`;
        dots.forEach(({ dot, lab }, i) => {
          const on = t >= at[i], p = ease.back(span(t, at[i], 0.35));
          dot.style.background = on ? 'var(--accent)' : '#fff';
          dot.style.scale = on ? `${1 + 0.35 * Math.sin(Math.PI * p)}` : '1';
          lab.style.opacity = i === reached ? 1 : 0.55;
          lab.style.color = i === reached ? 'var(--accent)' : '#fff';
        });
      },
    };
  };

  // Photo card: a real photo of what is said, framed and tilted beside the speaker, with a slow push and a label.
  T.photocard = (s, root) => {
    const [x, y, w, h] = s.box;
    const g = boxed(el('div', 'g photo-card', root), s.box);
    const frame = el('div', 'photo-frame', g);
    const img = el('img', '', frame);
    img.src = s.asset;
    let label = null;
    if (s.data.text) label = el('div', 'pill tag-pill photo-label', g, s.data.text);
    if (label) label.style.fontSize = `${Math.max(26, h * 0.075)}px`;
    const tilt = (s.id.charCodeAt(s.id.length - 1) % 2 ? 1 : -1) * 3;
    return {
      seek(t) {
        envelope(g, t, s.dur, { from: 0.55, blur: 8, rise: 50 });
        g.style.rotate = `${tilt * (1 - 0.4 * ease.out(span(t, 0, 0.5)))}deg`;
        img.style.transform = `scale(${1.04 + 0.08 * (t / Math.max(0.1, s.dur))})`;
        if (label) reveal(label, t, 0.25, { dy: 18 });
      },
    };
  };

  // Colour wash flash between steps.
  T.wash = (s, root) => {
    const f = el('div', 'full', root);
    f.style.background = `radial-gradient(80% 60% at 50% 45%, rgba(255,240,200,1) 0%, ${s.data.color || 'rgba(255,170,30,1)'} 55%, rgba(255,120,0,.9) 100%)`;
    return { seek(t) { f.style.opacity = t < 0.06 ? t / 0.06 : 1 - ease.out(span(t, 0.06, s.dur - 0.06)); } };
  };
})();
