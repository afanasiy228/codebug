(() => {
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const pointer = matchMedia('(hover: hover) and (pointer: fine)');
    const canvas = document.createElement('canvas');
    canvas.className = 'training-background';
    canvas.setAttribute('aria-hidden', 'true');
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const spacing = 32;
    const radius = 145;
    let width = 0, height = 0, frame = 0, lastTime = 0;
    let active = false, resizePending = true;
    let x = -1000, y = -1000, targetX = x, targetY = y;
    let strength = 0, targetStrength = 0;

    function schedule() {
        if (active && !frame && !document.hidden) frame = requestAnimationFrame(render);
    }

    function render(now) {
        frame = 0;
        if (!active) return;
        if (resizePending) {
            width = innerWidth;
            height = innerHeight;
            const dpr = Math.min(devicePixelRatio || 1, 1.5);
            canvas.width = Math.round(width * dpr);
            canvas.height = Math.round(height * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            resizePending = false;
        }
        const easing = 1 - Math.exp(-Math.min(now - lastTime || 16, 40) / 65);
        lastTime = now;
        x += (targetX - x) * easing;
        y += (targetY - y) * easing;
        strength += (targetStrength - strength) * easing;
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = 'rgba(186, 168, 133, .14)';
        ctx.beginPath();
        for (let py = spacing / 2; py < height; py += spacing) {
            for (let px = spacing / 2; px < width; px += spacing) {
                const dx = px - x, dy = py - y;
                const distance = Math.hypot(dx, dy);
                // A small, smooth bulge; points return to their grid as the pointer leaves.
                const shift = distance > 0 && distance < radius
                    ? Math.sin(Math.PI * distance / radius) * 3.2 * strength / distance : 0;
                const dotX = px + dx * shift, dotY = py + dy * shift;
                ctx.moveTo(dotX + .8, dotY);
                ctx.arc(dotX, dotY, .8, 0, Math.PI * 2);
            }
        }
        ctx.fill();
        document.body.classList.add('training-dots-ready');
        if (Math.abs(targetX - x) + Math.abs(targetY - y) > .1 || Math.abs(targetStrength - strength) > .002) schedule();
    }

    function reset() {
        targetStrength = 0;
        schedule();
    }

    function updateMode() {
        active = !motion.matches && pointer.matches;
        if (active) {
            if (!canvas.isConnected) document.body.prepend(canvas);
            resizePending = true;
            schedule();
        } else {
            cancelAnimationFrame(frame);
            frame = 0;
            strength = targetStrength = 0;
            canvas.remove();
            document.body.classList.remove('training-dots-ready');
        }
    }

    document.addEventListener('pointermove', event => {
        if (!active || event.pointerType === 'touch') return;
        targetX = event.clientX;
        targetY = event.clientY;
        targetStrength = 1;
        schedule();
    }, { passive: true });
    document.addEventListener('pointerout', event => { if (!event.relatedTarget) reset(); });
    window.addEventListener('blur', reset);
    window.addEventListener('resize', () => { resizePending = true; schedule(); }, { passive: true });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(frame);
            frame = 0;
            strength = targetStrength = 0;
        } else schedule();
    });
    motion.addEventListener('change', updateMode);
    pointer.addEventListener('change', updateMode);
    updateMode();
})();
