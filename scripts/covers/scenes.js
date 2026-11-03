// Drawing code for generated profile covers. Runs inside a browser page:
// window.renderStill(name, w, h) draws a fractal, window.renderFrame(name, w, h, t)
// draws frame t in [0, 1) of a seamless loop.
(() => {
  const TAU = Math.PI * 2;

  function rng(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6D2B79F5) >>> 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function palette(stops) {
    // stops: [[pos, [r, g, b]], ...] -> f(x) for x in [0, 1]
    return (x) => {
      x = Math.max(0, Math.min(1, x));
      for (let i = 1; i < stops.length; i++) {
        if (x <= stops[i][0]) {
          const [p0, c0] = stops[i - 1], [p1, c1] = stops[i];
          const k = (x - p0) / (p1 - p0 || 1);
          return [0, 1, 2].map((j) => c0[j] + (c1[j] - c0[j]) * k);
        }
      }
      return stops[stops.length - 1][1];
    };
  }

  function canvas(w, h) {
    const c = document.getElementById('c');
    c.width = w; c.height = h;
    return c.getContext('2d');
  }

  // ---- fractals (escape-time, smooth colouring) ----
  function escapeImage(w, h, view, iter, step, colour) {
    const ctx = canvas(w, h);
    const img = ctx.createImageData(w, h);
    const { cx, cy, span } = view;
    const scale = span / w;
    for (let py = 0; py < h; py++) {
      for (let px = 0; px < w; px++) {
        const x0 = cx + (px - w / 2) * scale, y0 = cy + (py - h / 2) * scale;
        const v = step(x0, y0, iter);
        const [r, g, b] = colour(v);
        const o = (py * w + px) * 4;
        img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  function smooth(n, zr, zi, iter) {
    if (n >= iter) return -1;
    return n + 1 - Math.log(Math.log(Math.sqrt(zr * zr + zi * zi))) / Math.LN2;
  }

  const STILLS = {
    mandelbrot(w, h) {
      const pal = palette([[0, [8, 6, 4]], [0.25, [90, 40, 8]], [0.5, [245, 158, 11]], [0.7, [253, 230, 138]], [0.85, [180, 83, 9]], [1, [8, 6, 4]]]);
      escapeImage(w, h, { cx: -0.7436, cy: 0.1318, span: 0.012 }, 900, (x0, y0, it) => {
        let zr = 0, zi = 0, n = 0;
        while (n < it && zr * zr + zi * zi < 256) { const t = zr * zr - zi * zi + x0; zi = 2 * zr * zi + y0; zr = t; n++; }
        return smooth(n, zr, zi, it);
      }, (v) => v < 0 ? [6, 5, 4] : pal((v / 60) % 1));
    },
    julia(w, h) {
      const pal = palette([[0, [6, 4, 20]], [0.3, [67, 56, 202]], [0.55, [168, 85, 247]], [0.75, [244, 114, 182]], [0.9, [254, 240, 255]], [1, [6, 4, 20]]]);
      escapeImage(w, h, { cx: 0, cy: 0, span: 3.4 }, 400, (x, y, it) => {
        let zr = x, zi = y, n = 0;
        while (n < it && zr * zr + zi * zi < 256) { const t = zr * zr - zi * zi - 0.8; zi = 2 * zr * zi + 0.156; zr = t; n++; }
        return smooth(n, zr, zi, it);
      }, (v) => v < 0 ? [4, 3, 14] : pal(Math.pow((v % 48) / 48, 0.8)));
    },
    burning_ship(w, h) {
      const pal = palette([[0, [4, 2, 2]], [0.3, [127, 29, 29]], [0.55, [234, 88, 12]], [0.8, [250, 204, 21]], [1, [255, 251, 235]]]);
      escapeImage(w, h, { cx: -1.762, cy: -0.028, span: 0.11 }, 600, (x0, y0, it) => {
        let zr = 0, zi = 0, n = 0;
        while (n < it && zr * zr + zi * zi < 256) { const t = zr * zr - zi * zi + x0; zi = Math.abs(2 * zr * zi) + y0; zr = t; n++; }
        return smooth(n, zr, zi, it);
      }, (v) => v < 0 ? [3, 2, 2] : pal(Math.min(1, v / 70)));
    },
    newton(w, h) {
      const roots = [[1, 0], [-0.5, Math.sqrt(3) / 2], [-0.5, -Math.sqrt(3) / 2]];
      const colours = [[45, 212, 191], [99, 102, 241], [244, 114, 182]];
      const ctx = canvas(w, h);
      const img = ctx.createImageData(w, h);
      const span = 1.9, scale = span / w, cx = -0.15, cy = 0;
      for (let py = 0; py < h; py++) {
        for (let px = 0; px < w; px++) {
          let zr = cx + (px - w / 2) * scale, zi = cy + (py - h / 2) * scale, n = 0, root = -1;
          for (; n < 60; n++) {
            const r2 = zr * zr - zi * zi, i2 = 2 * zr * zi;          // z^2
            const r3 = r2 * zr - i2 * zi, i3 = r2 * zi + i2 * zr;   // z^3
            const dr = 3 * r2, di = 3 * i2, den = dr * dr + di * di || 1e-12;
            const nr = r3 - 1, ni = i3;                             // z^3 - 1
            zr -= (nr * dr + ni * di) / den;
            zi -= (ni * dr - nr * di) / den;
            for (let k = 0; k < 3; k++) if ((zr - roots[k][0]) ** 2 + (zi - roots[k][1]) ** 2 < 1e-6) root = k;
            if (root >= 0) break;
          }
          const shade = root < 0 ? 0 : 0.25 + 0.75 * (0.5 + 0.5 * Math.cos(n * 0.55));
          const [r, g, b] = root < 0 ? [0, 0, 0] : colours[root];
          const o = (py * w + px) * 4;
          img.data[o] = r * shade; img.data[o + 1] = g * shade; img.data[o + 2] = b * shade; img.data[o + 3] = 255;
        }
      }
      ctx.putImageData(img, 0, 0);
    },
    fern(w, h) {
      const ctx = canvas(w, h);
      const g = ctx.createLinearGradient(0, 0, w, h);
      g.addColorStop(0, '#03140c'); g.addColorStop(1, '#0b2a1b');
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      const rand = rng(7);
      const draw = (ox, oy, size, rot, alpha) => {
        let x = 0, y = 0;
        ctx.fillStyle = `rgba(134, 239, 172, ${alpha})`;
        for (let i = 0; i < 260000; i++) {
          const r = rand();
          let nx, ny;
          if (r < 0.01) { nx = 0; ny = 0.16 * y; }
          else if (r < 0.86) { nx = 0.85 * x + 0.04 * y; ny = -0.04 * x + 0.85 * y + 1.6; }
          else if (r < 0.93) { nx = 0.2 * x - 0.26 * y; ny = 0.23 * x + 0.22 * y + 1.6; }
          else { nx = -0.15 * x + 0.28 * y; ny = 0.26 * x + 0.24 * y + 0.44; }
          x = nx; y = ny;
          const c = Math.cos(rot), s = Math.sin(rot);
          const X = ox + (x * c - y * s) * size, Y = oy - (x * s + y * c) * size;
          ctx.fillRect(X, Y, 1.1, 1.1);
        }
      };
      draw(w * 0.18, h * 1.05, h * 0.11, -0.5, 0.18);
      draw(w * 0.55, h * 1.1, h * 0.12, 0.35, 0.22);
      draw(w * 0.88, h * 1.02, h * 0.09, -0.15, 0.16);
    },
  };

  // ---- animated loops ----
  const STAR_CACHE = {};
  function stars(w, h, count, seed) {
    const key = `${w}x${h}:${seed}`;
    if (!STAR_CACHE[key]) {
      const r = rng(seed);
      STAR_CACHE[key] = Array.from({ length: count }, () => ({
        x: r() * w, y: r() * h, s: Math.pow(r(), 3) * 1.8 + 0.35, ph: r(), sp: 1 + Math.floor(r() * 3), hue: r(),
      }));
    }
    return STAR_CACHE[key];
  }

  const FRAMES = {
    starry_sky(w, h, t) {
      const ctx = canvas(w, h);
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, '#050816'); g.addColorStop(0.6, '#13123a'); g.addColorStop(1, '#2a1846');
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      const glow = ctx.createRadialGradient(w * 0.75, h * 1.1, 0, w * 0.75, h * 1.1, h * 1.4);
      glow.addColorStop(0, 'rgba(244,114,182,.28)'); glow.addColorStop(1, 'rgba(244,114,182,0)');
      ctx.fillStyle = glow; ctx.fillRect(0, 0, w, h);
      for (const st of stars(w, h, Math.round(w * h / 700), 11)) {
        const tw = 0.45 + 0.55 * Math.pow(0.5 + 0.5 * Math.sin(TAU * (t * st.sp + st.ph)), 3);
        const col = st.hue < 0.15 ? '253,230,138' : st.hue < 0.3 ? '191,219,254' : '255,255,255';
        ctx.fillStyle = `rgba(${col},${tw})`;
        ctx.beginPath(); ctx.arc(st.x, st.y, st.s * 1.25, 0, TAU); ctx.fill();
        if (st.s > 1.1) {
          ctx.fillStyle = `rgba(${col},${tw * 0.18})`;
          ctx.beginPath(); ctx.arc(st.x, st.y, st.s * 4, 0, TAU); ctx.fill();
        }
      }
      // One shooting star per loop.
      const k = (t * 1.6) % 1;
      if (k < 0.35) {
        const p = k / 0.35, x = w * (0.15 + 0.5 * p), y = h * (0.12 + 0.3 * p);
        const tail = ctx.createLinearGradient(x, y, x - 140, y - 84);
        tail.addColorStop(0, `rgba(255,255,255,${0.9 * (1 - p)})`); tail.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.strokeStyle = tail; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 140, y - 84); ctx.stroke();
      }
    },
    honeycomb(w, h, t) {
      const ctx = canvas(w, h);
      ctx.fillStyle = '#0d0905'; ctx.fillRect(0, 0, w, h);
      const R = 34, hw = Math.sqrt(3) * R;
      for (let row = -1; row * R * 1.5 < h + R; row++) {
        for (let col = -1; col * hw < w + hw; col++) {
          const cx = col * hw + (row % 2 ? hw / 2 : 0), cy = row * R * 1.5;
          const wave = 0.5 + 0.5 * Math.sin(TAU * t - cx * 0.006 - cy * 0.011 + Math.sin(cx * 0.013) * 1.2);
          const a = 0.08 + 0.75 * Math.pow(wave, 4);
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const ang = TAU * i / 6 + Math.PI / 6;
            ctx.lineTo(cx + (R - 3) * Math.cos(ang), cy + (R - 3) * Math.sin(ang));
          }
          ctx.closePath();
          const fill = ctx.createLinearGradient(cx, cy - R, cx, cy + R);
          fill.addColorStop(0, `rgba(253,230,138,${a})`); fill.addColorStop(1, `rgba(217,119,6,${a * 0.8})`);
          ctx.fillStyle = fill; ctx.fill();
          ctx.strokeStyle = `rgba(251,191,36,${0.18 + 0.4 * wave})`; ctx.lineWidth = 1.2; ctx.stroke();
        }
      }
    },
    terminal(w, h, t) {
      const ctx = canvas(w, h);
      ctx.fillStyle = '#05070a'; ctx.fillRect(0, 0, w, h);
      const lines = [
        '$ g++ -O2 -std=c++17 main.cpp -o main', 'main.cpp:42:17: warning: comparison of integers of different signs',
        '$ ./main < tests/001', 'OK  test 001   12 ms   3.1 MB', 'OK  test 002   15 ms   3.2 MB', 'WA  test 003   expected 7, found 2',
        '$ git diff --stat', ' solutions/main.cpp | 1 +', '$ ./judge 87', 'push(v, l, r);  // found it', 'OK  20/20 tests passed',
        '$ codebug submit --task 87', 'Accepted  +12 EXP', '$ make test', 'ran 263 tests in 10.4s', 'OK',
      ];
      const lh = 24, total = lines.length * lh, off = t * total;
      ctx.font = '16px Menlo, Consolas, monospace';
      for (let i = -1; i <= Math.ceil(h / lh) + 1; i++) {
        const idx = ((Math.floor(off / lh) + i) % lines.length + lines.length) % lines.length;
        const y = i * lh - (off % lh) + 30;
        const text = lines[idx];
        ctx.fillStyle = text.startsWith('WA') ? 'rgba(248,113,113,.85)' : text.startsWith('OK') || text.startsWith('Accepted') ? 'rgba(74,222,128,.85)' : text.startsWith('$') ? 'rgba(251,191,36,.9)' : 'rgba(203,213,225,.55)';
        ctx.fillText(text, 40, y);
      }
      // Cursor blinks twice per loop at the bottom line.
      if (Math.sin(TAU * t * 4) > 0) { ctx.fillStyle = 'rgba(251,191,36,.9)'; ctx.fillRect(40, h - 40, 10, 18); }
      ctx.fillStyle = 'rgba(0,0,0,.18)';
      for (let y = 0; y < h; y += 3) ctx.fillRect(0, y, w, 1);
      const v = ctx.createRadialGradient(w / 2, h / 2, h * 0.2, w / 2, h / 2, w * 0.7);
      v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.65)');
      ctx.fillStyle = v; ctx.fillRect(0, 0, w, h);
    },
    synthwave(w, h, t) {
      const ctx = canvas(w, h);
      const horizon = h * 0.56;
      const sky = ctx.createLinearGradient(0, 0, 0, horizon);
      sky.addColorStop(0, '#0b0322'); sky.addColorStop(0.6, '#3b0a4f'); sky.addColorStop(1, '#a3195b');
      ctx.fillStyle = sky; ctx.fillRect(0, 0, w, horizon);
      for (const st of stars(w, horizon * 0.8, Math.round(w * h / 3500), 31)) {
        ctx.fillStyle = `rgba(255,255,255,${0.3 + 0.5 * (0.5 + 0.5 * Math.sin(TAU * (t * st.sp + st.ph)))})`;
        ctx.fillRect(st.x, st.y, st.s, st.s);
      }
      // Striped sun sitting on the horizon.
      const R = h * 0.36, sx = w * 0.5, sy = horizon;
      const sun = ctx.createLinearGradient(0, sy - R, 0, sy);
      sun.addColorStop(0, '#fde047'); sun.addColorStop(1, '#f43f5e');
      ctx.save();
      ctx.beginPath(); ctx.arc(sx, sy, R, Math.PI, 0); ctx.closePath(); ctx.clip();
      ctx.fillStyle = sun; ctx.fillRect(sx - R, sy - R, 2 * R, R);
      ctx.fillStyle = '#3b0a4f';
      for (let i = 0; i < 7; i++) {
        const y = sy - R * 0.55 + i * R * 0.085 + ((t * R * 0.085) % (R * 0.085));
        ctx.fillRect(sx - R, y, 2 * R, 2 + i * 1.3);
      }
      ctx.restore();
      const glow = ctx.createRadialGradient(sx, sy, R * 0.6, sx, sy, R * 2.2);
      glow.addColorStop(0, 'rgba(244,63,94,.35)'); glow.addColorStop(1, 'rgba(244,63,94,0)');
      ctx.fillStyle = glow; ctx.fillRect(0, 0, w, horizon);
      // Ground with a perspective grid that scrolls one row per loop.
      const ground = ctx.createLinearGradient(0, horizon, 0, h);
      ground.addColorStop(0, '#1a0526'); ground.addColorStop(1, '#05010d');
      ctx.fillStyle = ground; ctx.fillRect(0, horizon, w, h - horizon);
      ctx.strokeStyle = 'rgba(236,72,153,.85)'; ctx.lineWidth = 1.6;
      for (let k = -24; k <= 24; k++) {
        ctx.beginPath(); ctx.moveTo(sx + k * 14, horizon); ctx.lineTo(sx + k * w * 0.12, h); ctx.stroke();
      }
      for (let i = 0; i < 14; i++) {
        const z = (i + 1 - t) / 14;
        const y = horizon + (h - horizon) * Math.pow(z, 2.2);
        ctx.globalAlpha = 0.25 + 0.75 * z;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }
      ctx.globalAlpha = 1;
      ctx.fillStyle = 'rgba(34,211,238,.9)'; ctx.fillRect(0, horizon - 1, w, 2);
    },
    fireflies(w, h, t) {
      const ctx = canvas(w, h);
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, '#04110b'); g.addColorStop(1, '#0d2016');
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      for (const f of stars(w, h, 70, 41)) {
        const x = f.x + 40 * Math.sin(TAU * (t * f.sp + f.ph));
        const y = f.y + 26 * Math.cos(TAU * (t * f.sp + f.ph * 1.7));
        const a = Math.pow(0.5 + 0.5 * Math.sin(TAU * (t * f.sp * 2 + f.ph)), 2);
        const r = 10 + f.s * 6;
        const glow = ctx.createRadialGradient(x, y, 0, x, y, r);
        glow.addColorStop(0, `rgba(253,224,71,${0.9 * a})`); glow.addColorStop(0.3, `rgba(190,242,100,${0.35 * a})`); glow.addColorStop(1, 'rgba(190,242,100,0)');
        ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
      }
    },
  };

  window.renderStill = (name, w, h) => STILLS[name](w, h);
  window.renderFrame = (name, w, h, t) => FRAMES[name](w, h, t);
  window.coverNames = { stills: Object.keys(STILLS), frames: Object.keys(FRAMES) };
})();
