// Explainer scenes: what is being explained, shown as a small 3D world (Three.js, WebGL) and cut to full frame
// while the voice carries on. The director picks a shot (reveal, inside, compare, many, force, transform, flow,
// scale, wrong, location), a world (sky, space, macro, body, ocean, room, studio, city) and the actors: built 3D
// forms (cloud, raindrop, sun, coin, atom...) or any kit 3D object as a picture in the world. Labels are pinned to
// what they name and typed in; a ✗ or ✓ stamp marks a wrong or right idea. Every frame is a pure function of t.
(() => {
  const { T, el, ease, span, clamp, rng } = window.BeatsKit;
  const TAU = Math.PI * 2;
  const lerp = (a, b, p) => a + (b - a) * p;
  const HERO = 2.8;  // world units: a hero actor's height

  /* ---------- renderer: one per page, reused by every scene ---------- */
  let renderer = null;
  function rendererFor(W, H) {
    if (!renderer) {
      renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      renderer.setPixelRatio(1);
    }
    renderer.setSize(W, H, false);
    return renderer;
  }
  // Object3D.clone() copies userData through JSON, which drops the actors' ticks and parts.
  function copy(o) {
    const keep = o.userData;
    o.userData = {};
    const c = o.clone();
    o.userData = keep;
    c.userData = { ...keep };
    return c;
  }
  function dispose(scene) {
    scene?.traverse(o => {
      o.geometry?.dispose();
      [].concat(o.material || []).forEach(m => { m.map?.dispose(); m.dispose(); });
    });
  }

  /* ---------- noise, textures, materials ---------- */
  function noiseOf(rand) {
    const perm = new Uint8Array(512), vals = new Float32Array(256);
    for (let i = 0; i < 256; i++) { perm[i] = i; vals[i] = rand(); }
    for (let i = 255; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [perm[i], perm[j]] = [perm[j], perm[i]]; }
    for (let i = 0; i < 256; i++) perm[i + 256] = perm[i];
    const at = (x, y, z) => vals[perm[perm[perm[x & 255] + (y & 255)] + (z & 255)]];
    const smooth = f => f * f * (3 - 2 * f);
    const noise = (x, y, z) => {
      const ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z);
      const u = smooth(x - ix), v = smooth(y - iy), w = smooth(z - iz);
      const a = lerp(lerp(at(ix, iy, iz), at(ix + 1, iy, iz), u), lerp(at(ix, iy + 1, iz), at(ix + 1, iy + 1, iz), u), v);
      const b = lerp(lerp(at(ix, iy, iz + 1), at(ix + 1, iy, iz + 1), u), lerp(at(ix, iy + 1, iz + 1), at(ix + 1, iy + 1, iz + 1), u), v);
      return lerp(a, b, w);
    };
    return (x, y, z, octaves = 4) => {
      let sum = 0, amp = 0.5, f = 1;
      for (let o = 0; o < octaves; o++) { sum += amp * noise(x * f, y * f, z * f); amp *= 0.5; f *= 2.03; }
      return sum / (1 - Math.pow(0.5, octaves));
    };
  }
  function canvasTexture(size, draw, repeat = false) {
    const c = document.createElement('canvas');
    c.width = c.height = size;
    draw(c.getContext('2d'), size);
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    if (repeat) tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    return tex;
  }
  const radial = (stops) => canvasTexture(256, (g, s) => {
    const r = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    stops.forEach(([at, color]) => r.addColorStop(at, color));
    g.fillStyle = r;
    g.fillRect(0, 0, s, s);
  });
  const clay = (color, more = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.88, metalness: 0, ...more });
  const glossy = (color, more = {}) => new THREE.MeshPhysicalMaterial({ color, roughness: 0.12, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.06, ...more });
  // A glow that is strongest at the edges: bubbles, x-ray shells, atmospheres, cells.
  function fresnel(color, { power = 2.2, base = 0.08, strength = 1.2, opacity = 1, additive = false } = {}) {
    return new THREE.ShaderMaterial({
      uniforms: { color: { value: new THREE.Color(color) }, power: { value: power }, base: { value: base }, strength: { value: strength }, opacity: { value: opacity } },
      vertexShader: `varying vec3 vN; varying vec3 vV;
        void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform vec3 color; uniform float power; uniform float base; uniform float strength; uniform float opacity; varying vec3 vN; varying vec3 vV;
        void main() { float f = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), power); gl_FragColor = vec4(color * (0.6 + f), clamp(base + f * strength, 0.0, 1.0) * opacity);
        #include <colorspace_fragment>
        }`,
      transparent: true, depthWrite: false, blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
    });
  }
  function skyDome(top, bottom, exponent = 0.8) {
    return new THREE.Mesh(new THREE.SphereGeometry(400, 32, 16), new THREE.ShaderMaterial({
      uniforms: { top: { value: new THREE.Color(top) }, bottom: { value: new THREE.Color(bottom) }, exponent: { value: exponent } },
      vertexShader: 'varying vec3 vP; void main() { vP = (modelMatrix * vec4(position, 1.0)).xyz; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
      fragmentShader: `uniform vec3 top; uniform vec3 bottom; uniform float exponent; varying vec3 vP;
        void main() { float h = normalize(vP).y; gl_FragColor = vec4(mix(bottom, top, pow(max(h * 0.5 + 0.5, 0.0), exponent)), 1.0);
        #include <colorspace_fragment>
        }`,
      side: THREE.BackSide, depthWrite: false, fog: false,
    }));
  }
  const ball = (r, detail = 64) => new THREE.SphereGeometry(r, detail, Math.round(detail * 0.75));
  function displaced(geometry, fbm, amount, scale = 1.4, flatBottom = null) {
    const p = geometry.attributes.position, v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i);
      const n = fbm(v.x * scale + 7, v.y * scale + 3, v.z * scale + 11);
      v.multiplyScalar(1 + (n - 0.5) * amount);
      if (flatBottom !== null && v.y < flatBottom) v.y = lerp(v.y, flatBottom, 0.75);
      p.setXYZ(i, v.x, v.y, v.z);
    }
    geometry.computeVertexNormals();
    return geometry;
  }

  /* ---------- forms: built 3D actors, each normalised to height 1 ---------- */
  function normalised(inner, extra = {}) {
    const box = new THREE.Box3().setFromObject(inner), size = box.getSize(new THREE.Vector3()), centre = box.getCenter(new THREE.Vector3());
    // Height 1, and never wider than the narrow frame holds (a cloud is wide, not tall).
    const k = 1 / Math.max(size.y, size.x / 0.85, 1e-3);
    inner.scale.multiplyScalar(k);
    inner.position.sub(centre.multiplyScalar(k));
    const outer = new THREE.Group();
    outer.add(inner);
    outer.userData = { width: size.x * k, ...extra };
    outer.traverse(o => { if (o.isMesh && !o.material.transparent) { o.castShadow = true; o.receiveShadow = true; } });
    return outer;
  }
  const teardrop = () => {
    const pts = [];
    for (let i = 0; i <= 48; i++) {
      const a = (i / 48) * Math.PI;
      pts.push(new THREE.Vector2(Math.sin(a) * Math.pow(Math.sin(a / 2), 1.6) * 0.8, Math.cos(a)));
    }
    return new THREE.LatheGeometry(pts, 48);
  };
  const water = () => glossy('#2f8ff0', { emissive: '#0b3a8a', emissiveIntensity: 0.35, transparent: true, opacity: 0.94 });
  function blobCloud(fbm, rand, color = '#f6f8fc') {
    const g = new THREE.Group(), mat = clay(color, { roughness: 0.96 });
    const puffs = [[0, 0.15, 0, 1], [-0.85, -0.05, 0.1, 0.72], [0.85, -0.02, -0.05, 0.75], [-0.4, 0.55, -0.1, 0.62],
      [0.45, 0.6, 0.05, 0.6], [0, -0.2, 0.55, 0.7], [-1.35, -0.25, 0, 0.5], [1.35, -0.2, 0.1, 0.52], [0.1, 0.85, -0.2, 0.45]];
    puffs.forEach(([x, y, z, r]) => {
      const m = new THREE.Mesh(displaced(ball(r * (0.9 + rand() * 0.2), 48), fbm, 0.22, 2.2, -0.15 / r), mat);
      m.position.set(x, y, z);
      g.add(m);
    });
    return g;
  }
  const FORMS = {
    cloud: ({ fbm, rand }) => {
      const shell = blobCloud(fbm, rand);
      const content = new THREE.Mesh(displaced(ball(0.95), fbm, 0.3, 2.6), water());
      content.scale.set(1.75, 0.85, 1.0);
      content.visible = false;
      const g = new THREE.Group();
      g.add(shell, content);
      return normalised(g, { shell, content, tick: (o, t) => { o.rotation.y = Math.sin(t * 0.4) * 0.12; } });
    },
    drop: () => {
      const m = new THREE.Mesh(teardrop(), glossy('#1d6ff2', { emissive: '#0a2f80', emissiveIntensity: 0.3, transparent: true, opacity: 0.95 }));
      const shine = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 12), new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0.7 }));
      shine.position.set(-0.22, -0.2, 0.42);
      shine.scale.set(0.8, 1.6, 0.4);
      const g = new THREE.Group();
      g.add(m, shine);
      return normalised(g, { tick: (o, t) => { o.children[0].children[0].scale.set(1 + Math.sin(t * 5) * 0.015, 1 - Math.sin(t * 5) * 0.015, 1); } });
    },
    droplet: () => normalised(new THREE.Mesh(new THREE.SphereGeometry(0.5, 32, 24), glossy('#3b9cff', { emissive: '#0b3a8a', emissiveIntensity: 0.3, transparent: true, opacity: 0.9 }))),
    bubble: () => {
      const g = new THREE.Group();
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.5, 32, 24), fresnel('#7cc4ff', { power: 2.6, base: 0.04, strength: 1.4 })));
      return normalised(g);
    },
    water: ({ fbm }) => normalised(new THREE.Mesh(displaced(ball(0.6), fbm, 0.3, 2.4), water()),
      { tick: (o, t) => { o.rotation.y = t * 0.3; } }),
    sun: () => {
      const g = new THREE.Group();
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.5, 48, 32), new THREE.MeshBasicMaterial({ color: '#ffd24a' })));
      const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: radial([[0, 'rgba(255,214,90,0.9)'], [0.35, 'rgba(255,160,40,0.45)'], [1, 'rgba(255,120,0,0)']]), depthWrite: false, blending: THREE.AdditiveBlending }));
      glow.scale.setScalar(2.4);
      g.add(glow);
      return normalised(g, { tick: () => undefined });
    },
    planet: ({ fbm }) => {
      const tex = canvasTexture(512, (g, s) => {
        const img = g.createImageData(s, s);
        for (let y = 0; y < s; y++) for (let x = 0; x < s; x++) {
          const lon = (x / s) * TAU, lat = (y / s) * Math.PI;
          const n = fbm(Math.sin(lat) * Math.cos(lon) * 2.2, Math.cos(lat) * 2.2, Math.sin(lat) * Math.sin(lon) * 2.2, 5);
          const land = n > 0.53, ice = Math.abs(y / s - 0.5) > 0.44, i = (y * s + x) * 4;
          const c = ice ? [235, 242, 248] : land ? (n > 0.62 ? [150, 130, 90] : [70, 140, 70]) : [24, 86, 170];
          img.data.set([...c, 255], i);
        }
        g.putImageData(img, 0, 0);
      });
      const g = new THREE.Group();
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.5, 64, 48), new THREE.MeshStandardMaterial({ map: tex, roughness: 0.8 })));
      const air = new THREE.Mesh(new THREE.SphereGeometry(0.53, 48, 32), fresnel('#6fb6ff', { power: 3, base: 0, strength: 1.3, additive: true }));
      g.add(air);
      return normalised(g, { globe: g.children[0], tick: (o, t, s) => { if (!s.place) o.children[0].rotation.y = t * 0.25; } });
    },
    moon: ({ fbm }) => normalised(new THREE.Mesh(displaced(ball(0.5), fbm, 0.06, 4), clay('#c9c6bf')),
      { tick: (o, t) => { o.rotation.y = t * 0.2; } }),
    coin: () => {
      const g = new THREE.Group(), gold = new THREE.MeshStandardMaterial({ color: '#f5bd2e', metalness: 0.3, roughness: 0.32, emissive: '#7a4a00', emissiveIntensity: 0.35 });
      const body = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.12, 64), gold);
      body.rotation.x = Math.PI / 2;
      const rim = new THREE.Mesh(new THREE.TorusGeometry(0.4, 0.025, 12, 64), gold);
      rim.position.z = 0.065;
      g.add(body, rim);
      return normalised(g, { tick: (o, t) => { o.rotation.y = t * 2.2; } });
    },
    block: ({ accent }) => normalised(new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1, 4, 4, 4), clay(accent, { roughness: 0.6 }))),
    rock: ({ fbm }) => normalised(new THREE.Mesh(displaced(new THREE.IcosahedronGeometry(0.5, 3), fbm, 0.6, 2), clay('#8d8a82', { flatShading: true }))),
    tree: ({ fbm }) => {
      const g = new THREE.Group(), leaf = clay('#4f8f37', { flatShading: true });
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.12, 0.5, 10), clay('#7a5236'));
      trunk.position.y = 0.25;
      g.add(trunk);
      [[0.75, 0.42], [1.05, 0.34], [1.3, 0.24]].forEach(([y, r]) => {
        const c = new THREE.Mesh(displaced(new THREE.ConeGeometry(r, 0.55, 9, 3), fbm, 0.15, 3), leaf);
        c.position.y = y;
        g.add(c);
      });
      return normalised(g, { tick: (o, t) => { o.rotation.z = Math.sin(t * 1.6) * 0.02; } });
    },
    mountain: ({ fbm }) => {
      const geo = displaced(new THREE.ConeGeometry(1, 1.2, 64, 16), fbm, 0.35, 1.6);
      const col = [], p = geo.attributes.position;
      for (let i = 0; i < p.count; i++) {
        const y = p.getY(i), c = new THREE.Color(y > 0.25 ? '#f4f6f8' : y > -0.15 ? '#8b8a82' : '#5d8f3a');
        col.push(c.r, c.g, c.b);
      }
      geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      return normalised(new THREE.Mesh(geo, clay('#ffffff', { vertexColors: true, flatShading: true })));
    },
    arrow: ({ accent }) => {
      const g = new THREE.Group(), mat = clay(accent, { emissive: accent, emissiveIntensity: 0.35, roughness: 0.5 });
      const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.7, 16), mat);
      const head = new THREE.Mesh(new THREE.ConeGeometry(0.24, 0.35, 24), mat);
      shaft.position.y = -0.17;
      head.position.y = 0.35;
      g.add(shaft, head);
      return normalised(g);
    },
    heat: ({ rand }) => {
      const g = new THREE.Group(), cols = [];
      const glow = new THREE.ShaderMaterial({
        uniforms: { color: { value: new THREE.Color('#ff2d55') } },
        vertexShader: 'varying float vY; void main() { vY = position.y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
        fragmentShader: `uniform vec3 color; varying float vY; void main() { gl_FragColor = vec4(color, 0.55 * smoothstep(0.5, -0.5, vY));
          #include <colorspace_fragment>
          }`,
        transparent: true, depthWrite: false, side: THREE.DoubleSide,
      });
      const arrowMat = clay('#ff1f4b', { emissive: '#ff1f4b', emissiveIntensity: 0.5 });
      for (let i = 0; i < 5; i++) {
        const c = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.2, 1, 24, 1, true), glow);
        c.position.set((i - 2) * 0.45, 0, (rand() - 0.5) * 0.6);
        const a = new THREE.Group();
        const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.16, 8), arrowMat);
        const head = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.09, 12), arrowMat);
        head.position.y = 0.11;
        a.add(shaft, head);
        a.position.copy(c.position);
        g.add(c, a);
        cols.push({ a, phase: rand() });
      }
      return normalised(g, { tick: (o, t) => cols.forEach(({ a, phase }) => { a.position.y = -0.45 + (((t * 0.55 + phase) % 1) * 0.9); }) });
    },
    flame: () => {
      const g = new THREE.Group();
      [['#ff5a1f', 1, 0.5], ['#ffb020', 0.7, 0.34], ['#fff1a8', 0.42, 0.18]].forEach(([c, h, r], i) => {
        const m = new THREE.Mesh(teardrop(), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.92 }));
        m.scale.set(r * 1.6, h, r * 1.6);
        m.position.set(0, -0.5 + h * 0.5, i * 0.02);
        g.add(m);
      });
      return normalised(g, { tick: (o, t) => o.children[0].children.forEach((m, i) => { m.scale.y = [1, 0.7, 0.42][i] * (1 + Math.sin(t * 11 + i) * 0.06); }) });
    },
    atom: ({ accent }) => {
      const g = new THREE.Group(), electrons = [];
      const nucleus = new THREE.Group();
      for (let i = 0; i < 9; i++) {
        const s = new THREE.Mesh(new THREE.SphereGeometry(0.11, 20, 16), glossy(i % 2 ? '#ff4d5a' : '#4d8dff'));
        s.position.set(Math.sin(i * 2.4) * 0.1, Math.cos(i * 1.7) * 0.1, Math.sin(i * 3.1) * 0.1);
        nucleus.add(s);
      }
      g.add(nucleus);
      [0, 1, 2].forEach(k => {
        const orbit = new THREE.Group();
        orbit.rotation.set(k * 1.05, k * 0.6, 0);
        orbit.add(new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.008, 8, 96), new THREE.MeshBasicMaterial({ color: '#9fc6ff', transparent: true, opacity: 0.6 })));
        const e = new THREE.Mesh(new THREE.SphereGeometry(0.045, 16, 12), new THREE.MeshBasicMaterial({ color: accent }));
        orbit.add(e);
        electrons.push({ e, k });
        g.add(orbit);
      });
      return normalised(g, { tick: (o, t) => electrons.forEach(({ e, k }) => { const a = t * (2.4 + k * 0.5) + k * 2; e.position.set(Math.cos(a) * 0.5, Math.sin(a) * 0.5, 0); }) });
    },
    molecule: ({ rand }) => {
      const g = new THREE.Group(), pts = [new THREE.Vector3()];
      for (let i = 1; i < 5; i++) pts.push(new THREE.Vector3((rand() - 0.5) * 1.1, (rand() - 0.5) * 1.1, (rand() - 0.5) * 0.6));
      pts.forEach((p, i) => {
        const s = new THREE.Mesh(new THREE.SphereGeometry(i ? 0.16 : 0.24, 24, 18), glossy(i ? '#e9edf3' : '#ff4d5a'));
        s.position.copy(p);
        g.add(s);
        if (i) {
          const bond = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, p.length(), 10), clay('#cfd6e0'));
          bond.position.copy(p.clone().multiplyScalar(0.5));
          bond.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), p.clone().normalize());
          g.add(bond);
        }
      });
      return normalised(g, { tick: (o, t) => { o.rotation.y = t * 0.6; o.rotation.x = Math.sin(t * 0.5) * 0.3; } });
    },
    cell: () => {
      const pts = [];
      for (let i = 0; i <= 32; i++) {
        const a = (i / 32) * Math.PI, r = Math.sin(a) * 0.5;
        pts.push(new THREE.Vector2(r, Math.cos(a) * (0.12 + 0.1 * Math.pow(r / 0.5, 6))));
      }
      const m = new THREE.Mesh(new THREE.LatheGeometry(pts, 48), glossy('#d8223f', { roughness: 0.35, clearcoat: 0.4 }));
      m.rotation.x = Math.PI / 2.4;
      return normalised(m, { tick: (o, t) => { o.rotation.z = t * 0.4; } });
    },
    germ: ({ fbm, rand }) => {
      const g = new THREE.Group(), body = new THREE.Mesh(displaced(ball(0.42, 48), fbm, 0.25, 3), glossy('#58c46a', { roughness: 0.4 }));
      g.add(body);
      for (let i = 0; i < 14; i++) {
        const d = new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).normalize();
        const spike = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 8), glossy('#e94c6b'));
        spike.position.copy(d.multiplyScalar(0.5));
        g.add(spike);
      }
      return normalised(g, { tick: (o, t) => { o.rotation.y = t * 0.5; } });
    },
    house: ({ accent }) => {
      const g = new THREE.Group();
      const body = new THREE.Mesh(new THREE.BoxGeometry(1, 0.7, 0.9), clay('#f1e7d6'));
      const roof = new THREE.Mesh(new THREE.ConeGeometry(0.82, 0.5, 4), clay(accent));
      roof.position.y = 0.6;
      roof.rotation.y = Math.PI / 4;
      const door = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.34, 0.02), clay('#6b4a32'));
      door.position.set(0, -0.18, 0.46);
      g.add(body, roof, door);
      return normalised(g);
    },
  };
  FORMS.raindrop = FORMS.drop;
  FORMS.earth = FORMS.planet;
  FORMS.fire = FORMS.flame;
  FORMS.bacteria = FORMS.virus = FORMS.germ;

  // Anything else: the kit's 3D object, standing in the world as a picture that always faces the camera.
  function spriteForm(texture) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true }));
    s.scale.setScalar(1.2);  // the kit's pictures carry a margin round the object
    const g = new THREE.Group();
    g.add(s);
    g.userData = { width: 1, sprite: s, tick: (o, t) => { s.material.rotation = Math.sin(t * 1.4) * 0.04; } };
    return g;
  }

  /* ---------- worlds ---------- */
  function lights(scene, { sky = '#bfe3ff', ground = '#4a5a3a', sun = '#fff1d6', power = 2.6, dir = [4, 9, 6] } = {}) {
    scene.add(new THREE.HemisphereLight(sky, ground, 1.1));
    const key = new THREE.DirectionalLight(sun, power);
    key.position.set(...dir);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    Object.assign(key.shadow.camera, { left: -6, right: 6, top: 6, bottom: -6, near: 0.5, far: 40 });
    key.shadow.radius = 6;
    scene.add(key);
    const rim = new THREE.DirectionalLight('#cfe4ff', 0.8);
    rim.position.set(-6, 3, -6);
    scene.add(rim);
  }
  function drifting(scene, make, n, rand, box, speed = 0.12) {
    const items = [];
    for (let i = 0; i < n; i++) {
      const o = make(i);
      const home = new THREE.Vector3(lerp(box[0], box[1], rand()), lerp(box[2], box[3], rand()), lerp(box[4], box[5], rand()));
      o.position.copy(home);
      scene.add(o);
      items.push({ o, home, phase: rand() * TAU });
    }
    return t => items.forEach(({ o, home, phase }) => {
      o.position.set(home.x + Math.sin(t * speed * 3 + phase) * 0.3, home.y + Math.sin(t * speed * 2 + phase * 2) * 0.25, home.z);
    });
  }
  function terrain(fbm, { size = 90, y = -4.2, sea = 0.0 } = {}) {
    const geo = new THREE.PlaneGeometry(size, size, 160, 160);
    geo.rotateX(-Math.PI / 2);
    const p = geo.attributes.position, col = [];
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i);
      let h = (fbm(x * 0.07, 0.5, z * 0.07, 5) - 0.47) * 7;
      if (h < sea) h = sea + (h - sea) * 0.25;
      p.setY(i, h);
      const c = new THREE.Color(h < sea + 0.15 ? '#c8b27a' : h > 1.6 ? '#8f8c84' : fbm(x * 0.4, 1, z * 0.4, 2) > 0.5 ? '#5f9a35' : '#4c8030');
      col.push(c.r, c.g, c.b);
    }
    geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    geo.computeVertexNormals();
    const land = new THREE.Mesh(geo, clay('#ffffff', { vertexColors: true }));
    land.receiveShadow = true;
    const sea_ = new THREE.Mesh(new THREE.PlaneGeometry(size, size), new THREE.MeshStandardMaterial({ color: '#1f6f78', roughness: 0.15, metalness: 0.1, transparent: true, opacity: 0.9 }));
    sea_.rotation.x = -Math.PI / 2;
    sea_.position.y = sea + 0.12;
    const g = new THREE.Group();
    g.add(land, sea_);
    g.position.y = y;
    return g;
  }
  function floor(color, y = -1.3, shadowOnly = false) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), shadowOnly ? new THREE.ShadowMaterial({ opacity: 0.22 }) : clay(color, { roughness: 0.95 }));
    m.rotation.x = -Math.PI / 2;
    m.position.y = y;
    m.receiveShadow = true;
    return m;
  }
  function points(n, rand, box, color, size, map) {
    const pos = [];
    for (let i = 0; i < n; i++) pos.push(lerp(box[0], box[1], rand()), lerp(box[2], box[3], rand()), lerp(box[4], box[5], rand()));
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    return new THREE.Points(geo, new THREE.PointsMaterial({ color, size, map, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true }));
  }
  const dot = () => radial([[0, 'rgba(255,255,255,1)'], [0.4, 'rgba(255,255,255,0.5)'], [1, 'rgba(255,255,255,0)']]);

  const STUDIO_PALETTES = [
    ['#cfe3ff', '#f3f7ff', '#e6edf8', '#7fb2ff'],
    ['#d3f5e4', '#f3fbf6', '#e3f1e8', '#5fcf98'],
    ['#ffe0cc', '#fff6ef', '#f6e7dc', '#ff9a62'],
    ['#e6dcff', '#f8f5ff', '#ece6f8', '#a184ff'],
  ];
  const WORLDS = {
    sky: (scene, { fbm, rand }) => {
      scene.add(skyDome('#2f7fd6', '#d6ecff', 0.9));
      scene.fog = new THREE.Fog('#cfe6fb', 30, 120);
      lights(scene);
      scene.add(terrain(fbm, { y: -6 }));
      const far = drifting(scene, i => {
        const c = blobCloud(fbm, rand);
        c.scale.setScalar(1.6 + rand() * 1.4);
        return c;
      }, 6, rand, [-26, 26, 2, 7, -48, -28], 0.05);
      return { floorY: -6, tick: far };
    },
    space: (scene, { rand }) => {
      scene.background = new THREE.Color('#02040b');
      lights(scene, { sky: '#3a4a7a', ground: '#000000', sun: '#ffffff', power: 3.2, dir: [6, 3, 5] });
      scene.add(points(2500, rand, [-120, 120, -80, 80, -160, -40], '#ffffff', 0.6, dot()));
      const neb = new THREE.Sprite(new THREE.SpriteMaterial({ map: radial([[0, 'rgba(90,70,200,0.35)'], [1, 'rgba(0,0,0,0)']]), depthWrite: false, blending: THREE.AdditiveBlending }));
      neb.scale.setScalar(90);
      neb.position.set(-20, 18, -100);
      scene.add(neb);
      return { floorY: null };
    },
    macro: (scene, { rand }) => {
      scene.add(skyDome('#0b2552', '#2462b0', 1.1));
      scene.fog = new THREE.Fog('#123a78', 6, 26);
      lights(scene, { sky: '#9cc8ff', ground: '#0a1f44', sun: '#e8f3ff', power: 2.2 });
      const tick = drifting(scene, () => {
        const b = new THREE.Mesh(new THREE.SphereGeometry(0.2 + rand() * 0.5, 24, 16), fresnel('#8fd0ff', { power: 2.4, base: 0.02, strength: 1.2, opacity: 0.8 }));
        return b;
      }, 46, rand, [-7, 7, -9, 9, -16, -2]);
      return { floorY: null, tick };
    },
    body: (scene, { rand }) => {
      scene.add(skyDome('#3d0711', '#a8293f', 1.0));
      scene.fog = new THREE.Fog('#5a0d1d', 5, 24);
      lights(scene, { sky: '#ffb3c0', ground: '#3d0711', sun: '#ffe1e6', power: 2.2 });
      const make = FORMS.cell({});
      const tick = drifting(scene, () => {
        const c = copy(make);
        c.scale.setScalar(0.8 + rand() * 0.7);
        c.rotation.set(rand() * 3, rand() * 3, 0);
        return c;
      }, 26, rand, [-7, 7, -9, 9, -18, -4]);
      return { floorY: null, tick };
    },
    ocean: (scene, { rand }) => {
      scene.add(skyDome('#0a7fa8', '#032b4a', 0.7));
      scene.fog = new THREE.Fog('#05486e', 6, 34);
      lights(scene, { sky: '#9fe7ff', ground: '#0b3a52', sun: '#e6fbff', power: 2.4, dir: [1, 10, 2] });
      scene.add(floor('#d6c08e', -3.2));
      const shafts = [];
      for (let i = 0; i < 6; i++) {
        const s = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 30), new THREE.MeshBasicMaterial({ color: '#bff3ff', transparent: true, opacity: 0.06, depthWrite: false, blending: THREE.AdditiveBlending }));
        s.position.set(-8 + i * 3.2, 6, -12 - rand() * 8);
        s.rotation.z = 0.25;
        scene.add(s);
        shafts.push(s);
      }
      const bubbles = points(260, rand, [-8, 8, -3, 12, -14, 2], '#dff8ff', 0.18, dot());
      scene.add(bubbles);
      return { floorY: -3.2, tick: t => { bubbles.position.y = (t * 0.8) % 3; shafts.forEach((s, i) => { s.material.opacity = 0.05 + Math.sin(t * 0.8 + i) * 0.02; }); } };
    },
    room: (scene, { rand, low }) => {
      scene.background = new THREE.Color('#2a1a0c');
      scene.fog = new THREE.Fog('#3a2614', 10, 30);
      scene.add(new THREE.HemisphereLight('#ffd9a0', '#2a1a0c', 0.5));
      const sun = new THREE.SpotLight('#ffcf8a', 120, 40, 0.5, 0.6, 1.4);
      sun.position.set(-6, 9, 4);
      sun.castShadow = true;
      sun.shadow.mapSize.set(1024, 1024);
      scene.add(sun);
      const wall = new THREE.Mesh(new THREE.PlaneGeometry(40, 20), clay('#a07a4c'));
      wall.position.set(0, 4, -6);
      wall.receiveShadow = true;
      scene.add(wall, floor('#6e5236', low ? -3.4 : -1.6));
      const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 3.2, 16, 24, 1, true), new THREE.MeshBasicMaterial({ color: '#ffdca0', transparent: true, opacity: 0.09, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide }));
      beam.position.set(-2.6, 4, -1);
      beam.rotation.z = 0.5;
      scene.add(beam);
      const dust = points(900, rand, [-6, 4, -1.5, 7, -5, 4], '#ffe2a8', 0.05, dot());
      scene.add(dust);
      return { floorY: low ? -3.4 : -1.6, tick: t => { dust.rotation.y = t * 0.03; dust.position.y = Math.sin(t * 0.3) * 0.15; } };
    },
    // The default for anything abstract: a clean coloured set (one of a few soft palettes) with a pale floor, a
    // glow behind the hero and a few out-of-focus orbs drifting in the back, so it never reads as an empty page.
    studio: (scene, { accent, low, rand }) => {
      const [top, bottom, ground, orb] = STUDIO_PALETTES[Math.floor(rand() * STUDIO_PALETTES.length)];
      scene.add(skyDome(top, bottom, 0.7));
      scene.fog = new THREE.Fog(bottom, 14, 40);
      lights(scene, { sky: '#ffffff', ground, sun: '#fff6ec', power: 2.5 });
      const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: radial([[0, 'rgba(255,255,255,0.85)'], [1, 'rgba(255,255,255,0)']]), depthWrite: false }));
      glow.scale.setScalar(9);
      glow.position.set(0, 0.6, -5);
      const y = low ? -3.4 : -1.3;
      scene.add(glow, floor(ground, y), floor('#000000', y + 0.01, true));
      const orbs = drifting(scene, i => {
        const m = new THREE.Mesh(new THREE.SphereGeometry(0.3 + rand() * 0.7, 32, 24), glossy(i % 3 ? orb : accent, { roughness: 0.25 }));
        return m;
      }, 7, rand, [-6, 6, -0.5, 6, -14, -7], 0.15);
      return { floorY: y, tick: orbs };
    },
    city: (scene, { rand, low }) => {
      scene.add(skyDome('#1c2c55', '#f0a35e', 0.9));
      scene.fog = new THREE.Fog('#c98a5c', 20, 70);
      lights(scene, { sky: '#ffc58a', ground: '#1c2233', sun: '#ffd2a0', power: 2.2, dir: [-6, 5, 4] });
      const y = low ? -3.4 : -1.4;
      scene.add(floor('#3a3f4c', y));
      const windows = canvasTexture(64, (g, s) => {
        g.fillStyle = '#2b3245';
        g.fillRect(0, 0, s, s);
        for (let y = 4; y < s; y += 10) for (let x = 4; x < s; x += 10) {
          g.fillStyle = rand() > 0.45 ? '#ffd98a' : '#3d465c';
          g.fillRect(x, y, 5, 6);
        }
      }, true);
      for (let i = 0; i < 40; i++) {
        const h = 2 + rand() * 9, w = 1 + rand() * 1.4;
        const tex = windows.clone();
        tex.repeat.set(w, h / 1.5);
        tex.needsUpdate = true;
        const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, w), new THREE.MeshStandardMaterial({ map: tex, emissive: '#ffffff', emissiveMap: tex, emissiveIntensity: 0.35, roughness: 0.8 }));
        b.position.set((rand() - 0.5) * 40, y + h / 2, -8 - rand() * 30);
        scene.add(b);
      }
      return { floorY: y };
    },
  };

  /* ---------- labels and stamps (HTML over the canvas) ---------- */
  function overlay(root, W, H, camera) {
    const layer = el('div', 'sc-layer', root);
    const items = [];
    const project = v => { const p = v.clone().project(camera); return { x: (p.x + 1) / 2 * W, y: (1 - p.y) / 2 * H, front: p.z < 1 }; };
    return {
      project,
      // A white box pinned to a point by a thin stem; it opens, its text types in, and it closes the same way.
      label(text, anchor, { at = 0.4, until = Infinity, tone = 'red', stem = 70, count = false } = {}) {
        if (!text) return;
        const g = el('div', `sc-label tone-${tone}`, layer);
        const box = el('div', 'sc-box', g), words = el('span', 'sc-text', box, text);
        const line = el('div', 'sc-stem', g), pin = el('div', 'sc-pin', g);
        box.style.minWidth = `${box.getBoundingClientRect().width}px`;
        const width = box.getBoundingClientRect().width, height = box.getBoundingClientRect().height;
        const number = count && text.match(/^([^\d]*)(\d[\d.,]{2,})(.*)$/);
        items.push(t => {
          const p = project(anchor()), open = ease.out(span(t, at, 0.16)), close = 1 - ease.out(span(t, until - 0.25, 0.22));
          const typed = clamp(span(t, at + 0.12, Math.min(0.5, 0.04 * text.length + 0.15))) * (1 - span(t, until - 0.45, 0.2));
          const x = clamp(p.x - width / 2, 36, W - 36 - width), top = clamp(p.y - stem - height, 60, H - height - 60);
          g.style.opacity = p.front ? Math.min(open, close) : 0;
          Object.assign(box.style, { left: `${x}px`, top: `${top}px`, transform: `scaleX(${Math.max(0.02, Math.min(open, close))})` });
          if (number) {
            const target = parseFloat(number[2].replace(/,/g, '')), v = target * ease.expo(span(t, at + 0.1, 0.9));
            words.textContent = number[1] + (Number.isInteger(target) ? Math.round(v).toLocaleString('en-IN') : v.toFixed(1)) + number[3];
          } else {
            words.textContent = text.slice(0, Math.round(typed * text.length));
          }
          const stemTop = top + height, stemLen = Math.max(0, p.y - stemTop);
          Object.assign(line.style, { left: `${p.x - 1.5}px`, top: `${stemTop}px`, height: `${stemLen * clamp(open * 1.4)}px` });
          Object.assign(pin.style, { left: `${p.x - 7}px`, top: `${p.y - 7}px` });
        });
      },
      stamp(kind, anchor, at) {
        const g = el('div', `sc-stamp sc-${kind}`, layer, kind === 'check' ? '✓' : '✕');
        items.push(t => {
          const p = project(anchor()), k = span(t, at, 0.22);
          g.style.opacity = k > 0 ? 1 : 0;
          g.style.left = `${p.x}px`;
          g.style.top = `${p.y}px`;
          g.style.transform = `translate(-50%, -50%) rotate(-8deg) scale(${lerp(2.4, 1, ease.out(k))})`;
        });
      },
      flash(at = 0, length = 0.2) {
        const f = el('div', 'sc-flash', layer);
        items.push(t => { f.style.opacity = t < at ? 0 : 1 - clamp(span(t, at, length)); });
      },
      seek: t => items.forEach(f => f(t)),
    };
  }

  /* ---------- shots: where the actors stand and what they do over time ---------- */
  const pop = (t, at, len = 0.45) => ease.back(span(t, at, len));
  const top = (o, k = 0.55) => () => o.localToWorld(new THREE.Vector3(0, k, 0));
  function place(o, x, y, z, size) { o.position.set(x, y, z); o.userData.size = size; o.scale.setScalar(0.0001); return o; }
  const grow = (o, p) => o.scale.setScalar(Math.max(0.0001, o.userData.size * p));
  const dirs = { up: [0, 1, 0], down: [0, -1, 0], left: [-1, 0, 0], right: [1, 0, 0], in: [0, 0, -1], out: [0, 0, 1] };

  const SHOTS = {
    reveal({ actors, ui, dur, s }) {
      const [a, ...rest] = actors;
      place(a, 0, 0.2, 0, HERO);
      const spots = [[-0.95, -1.15, 1.3], [0.95, -1.05, 1.1], [0, 1.95, -0.4]];
      rest.slice(0, 3).forEach((o, i) => place(o, ...spots[i], HERO * 0.38));
      ui.label(a.userData.label, top(a), { at: 0.45, until: dur, tone: a.userData.tone, count: true });
      rest.slice(0, 3).forEach((o, i) => ui.label(o.userData.label, top(o, 0.6), { at: 0.8 + i * 0.35, until: dur, tone: 'blue', stem: 40 }));
      return t => {
        grow(a, pop(t, 0.05));
        a.position.y = 0.2 + Math.sin(t * 1.6) * 0.05;
        rest.slice(0, 3).forEach((o, i) => grow(o, pop(t, 0.6 + i * 0.3)));
      };
    },
    inside({ actors, ui, dur, make, s }) {
      const [a] = actors;
      let b = actors[1] || a.userData.content;
      place(a, 0, 0.2, 0, HERO * 1.05);
      const open = Math.max(0.6, dur * 0.32);
      if (b && b !== a.userData.content) place(b, 0, 0.2, 0.35, HERO * 0.55);
      if (b === a.userData.content) b.visible = true;
      const shellMats = [];
      (a.userData.shell || a).traverse(o => { if (o.isMesh || o.isSprite) { o.material = o.material.clone(); o.material.transparent = true; shellMats.push(o.material); } });
      const lens = !a.userData.shell && new THREE.Mesh(new THREE.SphereGeometry(0.62, 48, 32), fresnel('#9fd4ff', { power: 2, base: 0.05, strength: 1.4 }));
      if (lens) { lens.scale.setScalar(0.0001); a.parent.add(lens); lens.position.copy(a.position); }
      ui.label(a.userData.label && actors[1] ? a.userData.label : '', top(a), { at: 0.3, until: open, tone: 'blue', stem: 40 });
      const named = actors[1]?.userData.label || a.userData.label;
      ui.label(named, () => (b === a.userData.content ? a.localToWorld(new THREE.Vector3(0, 0.38, 0)) : top(b, 0.6)()), { at: open + 0.35, until: dur, tone: 'red', count: true });
      return t => {
        grow(a, pop(t, 0.05));
        const x = ease.inOut(span(t, open, 0.6));
        shellMats.forEach(m => { m.opacity = lerp(1, a.userData.shell ? 0.18 : 0.25, x); });
        if (b === a.userData.content) b.scale.set(1.75 * x + 1e-4, 0.85 * x + 1e-4, 1.0 * x + 1e-4);
        else if (b) grow(b, ease.back(span(t, open + 0.1, 0.5)));
        if (lens) lens.scale.setScalar(HERO * 0.62 * ease.back(span(t, open, 0.5)) + 1e-4);
      };
    },
    compare({ actors, ui, dur, s }) {
      const [a, b] = actors;
      const r = clamp(s.ratio || 0.35, 0.08, 8), big = HERO * 0.95;
      const sa = r <= 1 ? big : big / r, sb = r <= 1 ? big * r : big;
      place(a, -0.62 - sa * 0.18, -0.2 + sa / 2 - big / 2, 0, sa);
      place(b || a, 0.62 + sb * 0.18, -0.2 + sb / 2 - big / 2, 0, sb);
      ui.label(a.userData.label, top(a, 0.6), { at: 0.45, until: dur, tone: 'blue' });
      if (b) ui.label(b.userData.label, top(b, 0.6), { at: 0.95, until: dur, tone: 'red' });
      return t => { grow(a, pop(t, 0.05)); if (b) grow(b, pop(t, 0.5)); };
    },
    many({ actors, ui, dur, s, rand, scene }) {
      const [a] = actors, n = Math.min(110, Math.max(24, s.count || 70));
      const copies = [a];
      for (let i = 1; i < n; i++) { const c = copy(a); scene.add(c); copies.push(c); }
      copies.forEach((c, i) => {
        const z = i === 0 ? 1.2 : lerp(-9, 2.5, rand()), spread = 2.2 + (2.5 - z) * 0.4;
        place(c, i === 0 ? 0.3 : (rand() - 0.5) * spread * 2, i === 0 ? 0.3 : (rand() - 0.5) * spread * 3.4, z, HERO * (i === 0 ? 0.32 : 0.12 + rand() * 0.16));
        c.userData.at = i === 0 ? 0.15 : rand() * Math.min(1.1, dur * 0.4);
        c.userData.phase = rand() * TAU;
      });
      ui.label(s.number || a.userData.label, top(a, 0.7), { at: 0.6, until: dur, tone: a.userData.tone || 'blue', count: true });
      return t => copies.forEach(c => {
        grow(c, pop(t, c.userData.at, 0.4));
        c.position.y += Math.sin(t * 0.9 + c.userData.phase) * 0.002;
      });
    },
    force({ actors, ui, dur, s, make }) {
      const [a] = actors, d = new THREE.Vector3(...(dirs[s.direction] || dirs.up));
      const cause = actors[1] || make({ form: 'arrow' });
      place(a, 0, 0.3, 0, HERO * 0.6);
      const isHeat = cause.userData.form === 'heat';
      const pushers = [cause];
      if (!isHeat) for (let i = 1; i < 3; i++) { const c = copy(cause); a.parent.add(c); pushers.push(c); }
      pushers.forEach((p, i) => {
        const side = new THREE.Vector3(d.y !== 0 ? (i - 1) * 1.1 : 0, d.x !== 0 ? (i - 1) * 1.1 : 0, 0);
        place(p, ...side.add(d.clone().multiplyScalar(isHeat ? -1.6 : -1.9)).add(new THREE.Vector3(0, 0.5, 0)).toArray(), isHeat ? HERO * 1.1 : HERO * 0.38);
        if (!isHeat && cause.userData.form === 'arrow') p.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d);
        p.userData.base = p.position.clone();
      });
      const go = Math.max(0.5, dur * 0.3);
      ui.label(actors[1]?.userData.label || '', () => pushers[0].localToWorld(new THREE.Vector3(0, 0.2, 0)), { at: 0.35, until: dur, tone: 'red' });
      ui.label(a.userData.label, top(a), { at: go + 0.4, until: dur, tone: 'blue', stem: 50 });
      const start = a.position.clone();
      return t => {
        grow(a, pop(t, 0.05));
        pushers.forEach((p, i) => grow(p, pop(t, 0.2 + i * 0.12)));
        const k = s.direction === 'down' ? Math.pow(span(t, go, dur - go), 2) : ease.inOut(span(t, go, dur - go));
        a.position.copy(start).addScaledVector(d, k * 1.0);
        if (!isHeat) pushers.forEach(p => p.position.copy(p.userData.base).addScaledVector(d, k * 1.0));
      };
    },
    transform({ actors, ui, dur, rand, scene }) {
      const [a] = actors, b = actors[1] || copy(a), bits = [];
      if (!actors[1]) scene.add(b);
      for (let i = 0; i < 10; i++) {
        const c = copy(a), ang = (i / 10) * TAU + rand() * 0.4, r = 1.6 + rand() * 0.9;
        scene.add(c);
        place(c, Math.cos(ang) * r, 0.3 + Math.sin(ang) * r * 1.3, (rand() - 0.5) * 1.5, HERO * 0.22);
        c.userData.home = c.position.clone();
        bits.push(c);
      }
      place(b, 0, 0.3, 0, HERO * 0.95);
      const meet = Math.max(0.6, dur * 0.45), centre = new THREE.Vector3(0, 0.3, 0);
      ui.label(b.userData.label || a.userData.label, top(b), { at: meet + 0.3, until: dur, tone: 'blue' });
      ui.flash(meet, 0.25);
      return t => {
        const k = ease.inOut(span(t, 0.25, meet - 0.25));
        bits.forEach((c, i) => {
          grow(c, pop(t, i * 0.04, 0.3) * (1 - span(t, meet - 0.1, 0.15)));
          c.position.lerpVectors(c.userData.home, centre, k);
        });
        grow(b, ease.back(span(t, meet, 0.5)));
      };
    },
    flow({ actors, ui, dur, s, scene, accent }) {
      const n = actors.length, loop = !!s.loop;
      const spots = actors.map((_, i) => loop
        ? new THREE.Vector3(Math.sin((i / n) * TAU) * 1.5, 0.3 + Math.cos((i / n) * TAU) * 2.1, 0)
        : new THREE.Vector3((i % 2 ? 0.6 : -0.6), 2.2 - (4.4 * i) / Math.max(1, n - 1), 0));
      actors.forEach((o, i) => place(o, ...spots[i].toArray(), HERO * (n > 3 ? 0.42 : 0.52)));
      const step = (dur - 1.0) / n, links = [];
      const linkMat = new THREE.MeshBasicMaterial({ color: accent });
      for (let i = 0; i < n - (loop ? 0 : 1); i++) {
        const a = spots[i], b = spots[(i + 1) % n], mid = a.clone().add(b).multiplyScalar(0.5).add(new THREE.Vector3(loop ? 0 : (i % 2 ? 0.9 : -0.9), 0, 0.6));
        const curve = new THREE.QuadraticBezierCurve3(a.clone().lerp(b, 0.22), mid, a.clone().lerp(b, 0.78));
        const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 48, 0.035, 8), linkMat);
        const head = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.22, 16), linkMat);
        scene.add(tube, head);
        links.push({ tube, head, curve, at: 0.3 + i * step + step * 0.5 });
      }
      actors.forEach((o, i) => ui.label(o.userData.label, top(o, 0.62), { at: 0.35 + i * step, until: dur, tone: i % 2 ? 'blue' : 'red', stem: 36 }));
      return t => {
        actors.forEach((o, i) => grow(o, pop(t, 0.1 + i * step)));
        links.forEach(({ tube, head, curve, at }) => {
          const p = ease.inOut(span(t, at, step * 0.6));
          tube.geometry.setDrawRange(0, Math.floor(p * 48) * 8 * 6);
          head.visible = p > 0.02;
          head.position.copy(curve.getPoint(p));
          head.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), curve.getTangent(Math.min(0.999, p)).normalize());
        });
      };
    },
    scale({ actors, ui, dur, s, scene, rand }) {
      // A pile that builds up row by row, bottom first, while the number counts up.
      const [a] = actors, rows = 6, pile = [];
      for (let row = 0; row < rows; row++) {
        for (let k = 0; k < rows - row; k++) {
          const c = pile.length ? copy(a) : a;
          if (pile.length) scene.add(c);
          c.userData.tick = null;
          c.rotation.y = (rand() - 0.5) * 0.5;
          place(c, (k - (rows - row - 1) / 2) * 0.54 + (rand() - 0.5) * 0.06, -1.0 + row * 0.5, (rand() - 0.5) * 0.4, HERO * 0.26);
          c.userData.at = 0.15 + (pile.length / 21) * dur * 0.55;
          pile.push(c);
        }
      }
      ui.label(s.number || a.userData.label, () => new THREE.Vector3(0, 2.2, 0), { at: 0.3, until: dur, tone: 'red', count: true, stem: 50 });
      return t => pile.forEach(c => grow(c, pop(t, c.userData.at, 0.3)));
    },
    wrong({ actors, ui, dur, s }) {
      const [a, b] = actors;
      place(a, 0, 0.2, 0, HERO);
      const hit = Math.max(0.6, dur * (b ? 0.3 : 0.45)), swap = dur * 0.58;
      ui.label(a.userData.label, top(a), { at: 0.3, until: b ? swap : dur, tone: 'blue', stem: 40 });
      ui.stamp('cross', () => a.localToWorld(new THREE.Vector3(0, 0, 0.4)), hit);
      if (b) {
        place(b, 0, 0.2, 0, HERO);
        ui.label(b.userData.label, top(b), { at: swap + 0.35, until: dur, tone: 'red' });
        ui.stamp('check', () => b.localToWorld(new THREE.Vector3(0.3, -0.3, 0.4)), swap + 0.6);
      }
      return t => {
        grow(a, pop(t, 0.05) * (b ? 1 - ease.inOut(span(t, swap - 0.2, 0.3)) : 1));
        a.position.x = b ? -2.6 * ease.inOut(span(t, swap - 0.2, 0.3)) : 0;
        if (b) grow(b, pop(t, swap));
      };
    },
    location({ actors, ui, dur, s, make }) {
      const globe = actors[0]?.userData.form === 'planet' ? actors[0] : make({ form: 'planet', label: s.place?.name || actors[0]?.userData.label });
      place(globe, 0, 0.2, 0, HERO);
      const lat = THREE.MathUtils.degToRad(s.place?.lat ?? 20), lon = THREE.MathUtils.degToRad(s.place?.lon ?? 78);
      const sphere = globe.userData.globe;
      const pin = new THREE.Group();
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.035, 16, 12), clay('#ff2d55', { emissive: '#ff2d55', emissiveIntensity: 0.4 }));
      const stick = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.08, 8), clay('#ffffff'));
      head.position.y = 0.09;
      stick.position.y = 0.04;
      pin.add(head, stick);
      const surface = new THREE.Vector3().setFromSphericalCoords(0.5, Math.PI / 2 - lat, Math.PI / 2 + lon);
      pin.position.copy(surface);
      pin.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), surface.clone().normalize());
      sphere.add(pin);
      const label = (s.place?.name || globe.userData.label || '').toUpperCase();
      ui.label(label, () => head.getWorldPosition(new THREE.Vector3()), { at: dur * 0.55, until: dur, tone: 'red', stem: 60 });
      return t => {
        grow(globe, pop(t, 0.05));
        const k = ease.inOut(span(t, 0.1, dur * 0.5));
        sphere.rotation.y = lerp(-Math.PI / 2 - lon - 2.2, -Math.PI / 2 - lon, k);
        sphere.rotation.x = lerp(0, lat * 0.85, k);
        pin.scale.setScalar(Math.max(1e-4, ease.back(span(t, dur * 0.5, 0.35))));
      };
    },
  };
  SHOTS.cycle = (ctx) => SHOTS.flow({ ...ctx, s: { ...ctx.s, loop: true } });

  /* ---------- the template ---------- */
  let previous = null;
  T.scene = (s, root) => {
    previous?.();
    const W = s.W, H = s.H, dur = s.dur, rand = rng(s.seed || s.id || 'scene');
    const r = rendererFor(W, H);
    root.appendChild(r.domElement);
    r.domElement.className = 'sc-canvas';
    const scene = new THREE.Scene(), fbm = noiseOf(rand), accent = s.accent || '#ffb020';
    const camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 900);
    const ctx = { fbm, rand, accent, low: ['flow', 'cycle'].includes(s.shot) };
    const world = (WORLDS[s.world] || WORLDS.studio)(scene, ctx);
    const loads = [];
    const make = spec => {
      let o;
      if (FORMS[spec.form]) o = FORMS[spec.form](ctx);
      else {
        const tex = new THREE.TextureLoader().load(spec.img || '', undefined, undefined, () => undefined);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.anisotropy = 4;
        loads.push(new Promise(res => { const check = () => (tex.image?.complete ? res() : setTimeout(check, 30)); check(); }));
        o = spriteForm(tex);
      }
      Object.assign(o.userData, { label: (spec.label || '').toUpperCase(), tone: spec.tone || 'red', form: spec.form || 'sprite' });
      o.scale.setScalar(0.0001);  // nothing shows until its shot places it
      scene.add(o);
      return o;
    };
    const actors = (s.actors || []).slice(0, 4).map(make);
    if (!actors.length) actors.push(make({ form: 'block' }));
    const ui = overlay(root, W, H, camera);
    const shot = (SHOTS[s.shot] || SHOTS.reveal)({ actors, ui, dur, s, rand, scene, make, accent });
    if (s.flash !== false) ui.flash(0, 0.18);
    // Pictures cast no shadow of their own: a soft contact shadow on the floor keeps them standing in the world.
    const shade = world.floorY != null && radial([[0, 'rgba(0,0,0,0.35)'], [1, 'rgba(0,0,0,0)']]);
    const shadows = shade ? scene.children.filter(o => o.userData.sprite).map(o => {
      const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: shade, transparent: true, depthWrite: false }));
      m.rotation.x = -Math.PI / 2;
      scene.add(m);
      return { o, m };
    }) : [];
    previous = () => dispose(scene);
    // The camera never stops: a slow push in and a small orbit, a touch more in the first half second.
    const tall = ['flow', 'cycle'].includes(s.shot), target = new THREE.Vector3(0, tall ? 0.1 : s.shot === 'scale' ? 0.4 : 0.3, 0);
    const dist = s.shot === 'many' ? 9.5 : tall ? 11.5 : 9, orbit = (rand() > 0.5 ? 1 : -1) * 0.22, lift = tall ? 0.2 : 0.7;
    return {
      ready: Promise.all(loads),
      seek(t) {
        const p = t / Math.max(dur, 0.1), push = ease.out(clamp(t / 0.6)) * 0.04 + p * 0.1;
        const yaw = lerp(-orbit, orbit, ease.inOut(p));
        const d = dist * (1.08 - push);
        camera.position.set(Math.sin(yaw) * d, target.y + lift + Math.sin(t * 0.7) * 0.05, Math.cos(yaw) * d);
        camera.lookAt(target);
        camera.updateMatrixWorld();
        world.tick?.(t);
        shadows.forEach(({ o, m }) => {
          const k = o.scale.x, lift = Math.max(0, o.position.y - k / 2 - world.floorY);
          m.position.set(o.position.x, world.floorY + 0.02, o.position.z);
          m.scale.setScalar(Math.max(1e-4, k * 0.9 * (1 + lift * 0.15)));
          m.material.opacity = clamp(1 - lift * 0.35);
        });
        shot(t);
        scene.traverse(o => o.userData.tick?.(o, t, s));
        r.render(scene, camera);
        ui.seek(t);
      },
    };
  };
})();
