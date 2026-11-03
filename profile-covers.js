/* Profile cover presets shared by the profile, rating and contest pages.
   Static covers are free; animated ones (shimmering gradients) need PRO+.
   The server keeps the same ids in PROFILE_COVER_PRESETS / PROFILE_COVER_ANIMATED. */
(function () {
    const COVERS = [
        { id: "amber_dusk", name: "Янтарный закат", bg: "linear-gradient(120deg,#1a0f05 0%,#b45309 55%,#fbbf24 100%)" },
        { id: "ember", name: "Тлеющий код", bg: "radial-gradient(circle at 78% 30%,rgba(245,158,11,.45),transparent 52%),radial-gradient(circle at 18% 85%,rgba(239,68,68,.28),transparent 55%),linear-gradient(135deg,#0e0b08,#1c1209)" },
        { id: "terminal", name: "Терминал", bg: "repeating-linear-gradient(0deg,rgba(255,255,255,.035) 0 1px,transparent 1px 4px),radial-gradient(circle at 80% 20%,rgba(74,222,128,.25),transparent 55%),linear-gradient(135deg,#04110a,#0d2a1a 60%,#14532d)" },
        { id: "blueprint", name: "Чертёж", bg: "linear-gradient(rgba(147,197,253,.14) 1px,transparent 1px) 0 0/28px 28px,linear-gradient(90deg,rgba(147,197,253,.14) 1px,transparent 1px) 0 0/28px 28px,linear-gradient(135deg,#0b1e3a,#163e6e)" },
        { id: "midnight", name: "Полночь", bg: "radial-gradient(ellipse at 72% 0%,rgba(99,102,241,.5),transparent 62%),radial-gradient(circle at 15% 90%,rgba(236,72,153,.22),transparent 50%),linear-gradient(180deg,#0b0b1a,#161036)" },
        { id: "northern", name: "Северный свет", bg: "linear-gradient(160deg,#04141a 8%,#0f766e 45%,#4c1d95 92%)" },
        { id: "sakura", name: "Сакура", bg: "radial-gradient(circle at 24% 32%,rgba(251,207,232,.75),transparent 44%),radial-gradient(circle at 76% 62%,rgba(249,168,212,.55),transparent 50%),linear-gradient(135deg,#3b1028,#9d174d)" },
        { id: "deep_sea", name: "Глубина", bg: "radial-gradient(ellipse at 50% -10%,rgba(56,189,248,.45),transparent 60%),linear-gradient(180deg,#0c4a6e,#082f49 55%,#020617)" },
        { id: "graphite", name: "Графит", bg: "repeating-linear-gradient(45deg,rgba(255,255,255,.03) 0 2px,transparent 2px 11px),linear-gradient(135deg,#111 0%,#2b2b2b 50%,#111 100%)" },
        { id: "crimson", name: "Баг найден", bg: "radial-gradient(circle at 84% 40%,rgba(239,68,68,.5),transparent 55%),linear-gradient(120deg,#0b0b0b,#450a0a)" },
        { id: "dunes", name: "Дюны", bg: "linear-gradient(172deg,#fde68a 0%,#f59e0b 32%,#92400e 68%,#1c0f05 100%)" },
        { id: "mint", name: "Мята", bg: "radial-gradient(circle at 85% 20%,rgba(167,243,208,.55),transparent 50%),linear-gradient(120deg,#022c22,#047857 60%,#34d399)" },
        { id: "lavender", name: "Лаванда", bg: "linear-gradient(120deg,#1e1b4b,#6d28d9 55%,#f0abfc)" },
        { id: "punchcard", name: "Перфокарта", bg: "radial-gradient(rgba(245,158,11,.28) 1.3px,transparent 1.8px) 0 0/16px 16px,linear-gradient(135deg,#120c05,#2e1c08)" },
        { id: "prism", name: "Призма", animated: true, bg: "linear-gradient(120deg,#f472b6,#a78bfa,#60a5fa,#34d399,#fbbf24,#f472b6) 0 50%/400% 400%" },
        { id: "aurora", name: "Сияние", animated: true, bg: "linear-gradient(120deg,#022c22,#0f766e,#4c1d95,#0e7490,#7c3aed,#022c22) 0 50%/400% 400%" },
        { id: "magma", name: "Магма", animated: true, bg: "linear-gradient(120deg,#1c0a00,#9a3412,#f59e0b,#dc2626,#7c2d12,#1c0a00) 0 50%/400% 400%" },
        { id: "neon", name: "Неон", animated: true, bg: "linear-gradient(120deg,#0f0c29,#ec4899,#302b63,#06b6d4,#a21caf,#0f0c29) 0 50%/400% 400%" },
        { id: "hologram", name: "Голограмма", animated: true, bg: "linear-gradient(120deg,#e0e7ff,#fbcfe8,#bae6fd,#ddd6fe,#fef3c7,#e0e7ff) 0 50%/400% 400%" },
        { id: "matrix", name: "Матрица", animated: true, bg: "repeating-linear-gradient(0deg,rgba(0,0,0,.3) 0 1px,transparent 1px 3px) 0 0/100% 100%,linear-gradient(180deg,#01140a,#22c55e,#01140a 30%,#01140a 55%,#4ade80,#01140a) 0 0/100% 400%" }
    ];
    const DEFAULT_ID = "amber_dusk";
    const byId = new Map(COVERS.map((cover) => [cover.id, cover]));

    // Animation keyframes are injected once; they run regardless of reduced-motion
    // on purpose: the shimmer is slow and is what PRO+ pays for.
    const style = document.createElement("style");
    style.textContent = `
        .cb-cover-anim { animation: cbCoverShift 16s ease-in-out infinite alternate; }
        .cb-cover-anim[data-cover="matrix"] { animation: cbCoverRain 9s linear infinite; }
        @keyframes cbCoverShift { from { background-position: 0% 50%; } to { background-position: 100% 50%; } }
        @keyframes cbCoverRain { from { background-position: 0 0, 0 0%; } to { background-position: 0 0, 0 100%; } }
    `;
    document.head.appendChild(style);

    function canUse(cover, level) {
        return !cover.animated || level === "pro_plus";
    }

    // The cover a user actually gets: unknown ids and animated covers without PRO+ fall back to the default.
    function resolve(id, level) {
        const cover = byId.get(String(id || "").toLowerCase());
        return cover && canUse(cover, level) ? cover : byId.get(DEFAULT_ID);
    }

    // Paints a preset onto an element (the background shorthand keeps per-layer sizes).
    function paint(el, cover) {
        if (!el || !cover) return;
        el.style.background = cover.bg;
        el.dataset.cover = cover.id;
        el.classList.toggle("cb-cover-anim", !!cover.animated);
    }

    function clear(el) {
        if (!el) return;
        el.classList.remove("cb-cover-anim");
        delete el.dataset.cover;
    }

    window.CodeBugCovers = { list: COVERS, defaultId: DEFAULT_ID, resolve, paint, clear, canUse };
})();
