// Contour-map background for the list pages: thin amber isolines of a slowly
// drifting field, with a small hill under the pointer. Animation does not depend
// on prefers-reduced-motion, by design: the drift is slow and the effect is subtle.
(() => {
    const canvas = document.createElement('canvas');
    canvas.className = 'training-background';
    canvas.setAttribute('aria-hidden', 'true');
    canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;z-index:-1;pointer-events:none;display:block';
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const coarse = matchMedia('(pointer: coarse)');
    // Finer cells give smoother isolines; touch screens get a lighter grid.
    const CELL = coarse.matches ? 14 : 10;
    const LEVELS = 9;
    const HILL = 0.16;
    const HILL_SPREAD = 6000;

    const perm = new Uint8Array(512);
    {
        const p = [...Array(256).keys()];
        for (let i = 255; i > 0; i--) {
            const j = (Math.random() * (i + 1)) | 0;
            [p[i], p[j]] = [p[j], p[i]];
        }
        for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
    }
    // Quintic fade keeps the field's slope continuous, so contours bend smoothly
    // instead of kinking at noise-cell borders.
    const fade = t => t * t * t * (t * (t * 6 - 15) + 10);
    const hash = (x, y, z) => perm[(perm[(perm[x & 255] + y) & 255] + z) & 255];
    function noise(x, y, z) {
        const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
        const u = fade(x - xi), v = fade(y - yi), w = fade(z - zi);
        const x0 = xi & 255, y0 = yi & 255, z0 = zi & 255, x1 = (xi + 1) & 255, y1 = (yi + 1) & 255, z1 = (zi + 1) & 255;
        const a = hash(x0, y0, z0), b = hash(x1, y0, z0), c = hash(x0, y1, z0), d = hash(x1, y1, z0);
        const e = hash(x0, y0, z1), f = hash(x1, y0, z1), g = hash(x0, y1, z1), h = hash(x1, y1, z1);
        const ab = a + (b - a) * u, cd = c + (d - c) * u, ef = e + (f - e) * u, gh = g + (h - g) * u;
        const front = ab + (cd - ab) * v, back = ef + (gh - ef) * v;
        return (front + (back - front) * w) / 255;
    }

    let width = 0, height = 0, cols = 0, rows = 0, field = null;
    let resizePending = true, lastDraw = 0, frame = 0;
    const pointer = { x: -9999, y: -9999, sx: -9999, sy: -9999, on: 0, son: 0 };

    function resize() {
        width = innerWidth;
        height = innerHeight;
        const dpr = Math.min(devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        cols = Math.ceil(width / CELL) + 1;
        rows = Math.ceil(height / CELL) + 1;
        field = new Float32Array(cols * rows);
        resizePending = false;
    }

    function draw(now) {
        const z = now * 0.00003;
        const hill = HILL * pointer.son;
        for (let j = 0; j < rows; j++) {
            for (let i = 0; i < cols; i++) {
                const x = i * CELL, y = j * CELL;
                let v = noise(x * 0.0028, y * 0.0028, z) * 0.82 + noise(x * 0.008, y * 0.008, z * 1.6) * 0.18;
                if (hill > 0.002) {
                    const dx = x - pointer.sx, dy = y - pointer.sy;
                    v += hill * Math.exp(-(dx * dx + dy * dy) / HILL_SPREAD);
                }
                field[j * cols + i] = v;
            }
        }
        ctx.clearRect(0, 0, width, height);
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        for (let level = 1; level < LEVELS; level++) {
            const iso = level / LEVELS * 1.05;
            const major = level % 4 === 0;
            ctx.strokeStyle = major ? 'rgba(232, 163, 58, .17)' : 'rgba(232, 163, 58, .065)';
            ctx.lineWidth = major ? 1.1 : 1;
            ctx.beginPath();
            for (let j = 0; j < rows - 1; j++) {
                for (let i = 0; i < cols - 1; i++) {
                    const a = field[j * cols + i], b = field[j * cols + i + 1];
                    const c = field[(j + 1) * cols + i + 1], d = field[(j + 1) * cols + i];
                    const code = (a > iso) | (b > iso) << 1 | (c > iso) << 2 | (d > iso) << 3;
                    if (code === 0 || code === 15) continue;
                    const x = i * CELL, y = j * CELL, t = (p, q) => (iso - p) / (q - p);
                    const top = [x + CELL * t(a, b), y], right = [x + CELL, y + CELL * t(b, c)];
                    const bottom = [x + CELL * t(d, c), y + CELL], left = [x, y + CELL * t(a, d)];
                    const seg = (p, q) => { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); };
                    switch (code) {
                        case 1: case 14: seg(left, top); break;
                        case 2: case 13: seg(top, right); break;
                        case 3: case 12: seg(left, right); break;
                        case 4: case 11: seg(right, bottom); break;
                        case 5: seg(left, top); seg(right, bottom); break;
                        case 6: case 9: seg(top, bottom); break;
                        case 7: case 8: seg(left, bottom); break;
                        case 10: seg(top, right); seg(left, bottom); break;
                    }
                }
            }
            ctx.stroke();
        }
    }

    function tick(now) {
        frame = requestAnimationFrame(tick);
        if (resizePending) resize();
        const dt = Math.min(60, now - (tick.last || now));
        tick.last = now;
        const k = 1 - Math.exp(-dt / 160);
        pointer.sx += (pointer.x - pointer.sx) * k;
        pointer.sy += (pointer.y - pointer.sy) * k;
        pointer.son += (pointer.on - pointer.son) * (1 - Math.exp(-dt / 420));
        // Every frame with a mouse for smooth motion; about 30 fps on touch screens.
        if (coarse.matches && now - lastDraw < 32) return;
        lastDraw = now;
        draw(now);
        document.body.classList.add('training-dots-ready');
    }

    function start() {
        if (!canvas.isConnected) document.body.prepend(canvas);
        if (!frame && !document.hidden) frame = requestAnimationFrame(tick);
    }

    document.addEventListener('pointermove', event => {
        if (event.pointerType === 'touch') return;
        pointer.x = event.clientX;
        pointer.y = event.clientY;
        if (pointer.sx < -999) { pointer.sx = pointer.x; pointer.sy = pointer.y; }
        pointer.on = 1;
    }, { passive: true });
    document.addEventListener('pointerout', event => { if (!event.relatedTarget) pointer.on = 0; });
    window.addEventListener('blur', () => { pointer.on = 0; });
    window.addEventListener('resize', () => { resizePending = true; }, { passive: true });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(frame);
            frame = 0;
        } else start();
    });
    if (document.body) start();
    else document.addEventListener('DOMContentLoaded', start);
})();
