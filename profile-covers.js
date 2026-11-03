/* Profile cover presets shared by the profile, rating and contest pages.
   Colours, gradients and fractals are free; shimmering gradients and live
   (animated image) covers need PRO+. The server keeps the same ids in
   PROFILE_COVER_PRESETS / PROFILE_COVER_PRO_PLUS. Images live in /covers and are
   built by scripts/covers/generate.js. */
(function () {
    const GROUPS = [
        { id: "color", title: "Цвета" },
        { id: "grad", title: "Градиенты" },
        { id: "fractal", title: "Фракталы" },
        { id: "flow", title: "Переливы", proPlus: true },
        { id: "live", title: "Живые", proPlus: true },
    ];

    const solid = (top, base) => `linear-gradient(180deg,${top} 0%,${base} 70%)`;
    const image = (name) => ({ bg: `url("/covers/${name}.webp") center/cover no-repeat`, thumb: `url("/covers/${name}.thumb.webp") center/cover no-repeat` });

    const COVERS = [
        { id: "color_amber", group: "color", name: "Янтарный", bg: solid("#f59e0b", "#b45309") },
        { id: "color_red", group: "color", name: "Красный", bg: solid("#ef4444", "#991b1b") },
        { id: "color_orange", group: "color", name: "Оранжевый", bg: solid("#f97316", "#c2410c") },
        { id: "color_green", group: "color", name: "Зелёный", bg: solid("#22c55e", "#15803d") },
        { id: "color_teal", group: "color", name: "Бирюзовый", bg: solid("#14b8a6", "#0f766e") },
        { id: "color_blue", group: "color", name: "Синий", bg: solid("#3b82f6", "#1d4ed8") },
        { id: "color_indigo", group: "color", name: "Индиго", bg: solid("#6366f1", "#3730a3") },
        { id: "color_purple", group: "color", name: "Фиолетовый", bg: solid("#a855f7", "#6b21a8") },
        { id: "color_pink", group: "color", name: "Розовый", bg: solid("#ec4899", "#9d174d") },
        { id: "color_graphite", group: "color", name: "Графит", bg: solid("#3f3f46", "#18181b") },

        { id: "grad_sunset", group: "grad", name: "Янтарный закат", bg: "linear-gradient(120deg,#1a0f05 0%,#b45309 55%,#fbbf24 100%)" },
        { id: "grad_northern", group: "grad", name: "Северный свет", bg: "linear-gradient(160deg,#04141a 8%,#0f766e 45%,#4c1d95 92%)" },
        { id: "grad_lavender", group: "grad", name: "Лаванда", bg: "linear-gradient(120deg,#1e1b4b,#6d28d9 55%,#f0abfc)" },
        { id: "grad_deep_sea", group: "grad", name: "Глубина", bg: "radial-gradient(ellipse at 50% -10%,rgba(56,189,248,.45),transparent 60%),linear-gradient(180deg,#0c4a6e,#082f49 55%,#020617)" },
        { id: "grad_sakura", group: "grad", name: "Сакура", bg: "radial-gradient(circle at 24% 32%,rgba(251,207,232,.75),transparent 44%),radial-gradient(circle at 76% 62%,rgba(249,168,212,.55),transparent 50%),linear-gradient(135deg,#3b1028,#9d174d)" },

        { id: "fractal_mandelbrot", group: "fractal", name: "Мандельброт", ...image("mandelbrot") },
        { id: "fractal_julia", group: "fractal", name: "Жюлиа", ...image("julia") },
        { id: "fractal_ship", group: "fractal", name: "Горящий корабль", ...image("burning_ship") },
        { id: "fractal_newton", group: "fractal", name: "Ньютон", ...image("newton") },
        { id: "fractal_fern", group: "fractal", name: "Папоротник", ...image("fern") },

        { id: "flow_prism", group: "flow", name: "Призма", animated: true, bg: "linear-gradient(120deg,#f472b6,#a78bfa,#60a5fa,#34d399,#fbbf24,#f472b6) 0 50%/400% 400%" },
        { id: "flow_aurora", group: "flow", name: "Сияние", animated: true, bg: "linear-gradient(120deg,#022c22,#0f766e,#4c1d95,#0e7490,#7c3aed,#022c22) 0 50%/400% 400%" },
        { id: "flow_magma", group: "flow", name: "Магма", animated: true, bg: "linear-gradient(120deg,#1c0a00,#9a3412,#f59e0b,#dc2626,#7c2d12,#1c0a00) 0 50%/400% 400%" },
        { id: "flow_neon", group: "flow", name: "Неон", animated: true, bg: "linear-gradient(120deg,#0f0c29,#ec4899,#302b63,#06b6d4,#a21caf,#0f0c29) 0 50%/400% 400%" },
        { id: "flow_hologram", group: "flow", name: "Голограмма", animated: true, bg: "linear-gradient(120deg,#e0e7ff,#fbcfe8,#bae6fd,#ddd6fe,#fef3c7,#e0e7ff) 0 50%/400% 400%" },

        { id: "live_sky", group: "live", name: "Звёздное небо", ...image("starry_sky") },
        { id: "live_honeycomb", group: "live", name: "Соты", ...image("honeycomb") },
        { id: "live_terminal", group: "live", name: "Терминал", ...image("terminal") },
        { id: "live_synthwave", group: "live", name: "Синтвейв", ...image("synthwave") },
        { id: "live_fireflies", group: "live", name: "Светлячки", ...image("fireflies") },
    ];
    const DEFAULT_ID = "grad_sunset";
    const PRO_PLUS_GROUPS = new Set(GROUPS.filter((g) => g.proPlus).map((g) => g.id));
    const byId = new Map(COVERS.map((cover) => [cover.id, cover]));

    // The shimmer runs regardless of reduced-motion on purpose: it is slow and is what PRO+ pays for.
    const style = document.createElement("style");
    style.textContent = `
        .cb-cover-anim { animation: cbCoverShift 16s ease-in-out infinite alternate; }
        @keyframes cbCoverShift { from { background-position: 0% 50%; } to { background-position: 100% 50%; } }
    `;
    document.head.appendChild(style);

    function proPlusOnly(cover) {
        return PRO_PLUS_GROUPS.has(cover.group);
    }

    function canUse(cover, level) {
        return !proPlusOnly(cover) || level === "pro_plus";
    }

    // The cover a user actually gets: unknown ids and PRO+ covers without PRO+ fall back to the default.
    function resolve(id, level) {
        const cover = byId.get(String(id || "").toLowerCase());
        return cover && canUse(cover, level) ? cover : byId.get(DEFAULT_ID);
    }

    // Paints a preset onto an element (the background shorthand keeps per-layer sizes).
    function paint(el, cover, options) {
        if (!el || !cover) return;
        el.style.background = (options && options.thumb && cover.thumb) || cover.bg;
        el.dataset.cover = cover.id;
        el.classList.toggle("cb-cover-anim", !!cover.animated);
    }

    function clear(el) {
        if (!el) return;
        el.classList.remove("cb-cover-anim");
        delete el.dataset.cover;
    }

    window.CodeBugCovers = { groups: GROUPS, list: COVERS, defaultId: DEFAULT_ID, resolve, paint, clear, canUse, proPlusOnly };
})();
