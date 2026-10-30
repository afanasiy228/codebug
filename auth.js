/* ============================
   FIREBASE INIT
============================ */
const db = (() => {
    try {
        if (window.db) return window.db;
        if (window.firebase && window.firebase.apps && window.firebase.apps.length) {
            return window.firebase.database();
        }
    } catch (err) {
        console.warn("Firebase DB init failed", err);
    }
    return null;
})();

function getDb() {
    return window.db || db || null;
}


/* ============================
   POST-LOGIN REDIRECT TARGET
============================ */
/**
 * Resolve the ?next= parameter to a safe destination.
 *
 * The raw value used to be assigned straight to location.href, which made
 * auth.html?next=https://evil.example/ an open redirect fired the instant a user
 * logged in, and auth.html?next=javascript:... script execution in this origin
 * while a fresh ID token sits in localStorage. Only same-origin relative paths
 * are accepted; anything else falls back to the home page.
 */
function safeNextTarget(rawNext, fallback) {
    const home = fallback || "index.html";
    const value = String(rawNext == null ? "" : rawNext).trim();
    if (!value) return home;
    // Reject anything with a scheme (javascript:, data:, https:), a protocol-relative
    // prefix, a backslash (which some browsers normalise to "/"), or a control char.
    if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return home;
    if (value.startsWith("//") || value.startsWith("\\")) return home;
    if (/[\u0000-\u001f\u007f]/.test(value)) return home;
    // Resolve the way the browser would, then confirm it stayed on this origin.
    try {
        const resolved = new URL(value, window.location.href);
        if (resolved.origin !== window.location.origin) return home;
    } catch (_) {
        return home;
    }
    // Safe: hand back the caller's own relative form, unchanged.
    return value;
}

if (typeof window !== "undefined") {
    window.safeNextTarget = safeNextTarget;
}

/* ============================
   USER SESSION
============================ */
function setUser(login) {
    if (!login) {
        localStorage.removeItem("user");
        return;
    }
    localStorage.setItem("user", login);
}

function getUser() {
    return localStorage.getItem("user");
}

function clearSession() {
    window.CodeBugData?.invalidate("private:");
    const previousLogin = localStorage.getItem("user");
    if (previousLogin) clearNavbarIdentityCache(previousLogin);
    localStorage.removeItem("user");
    localStorage.removeItem("uid");
    localStorage.removeItem("idToken");
}

async function logout() {
    try {
        const auth = getAuth();
        if (auth) await auth.signOut();
    } catch (err) {
        console.warn("Signout failed", err);
    }
    localStorage.setItem("forceSignout", "1");
    clearSession();
    window.location.href = "auth.html";
}

async function waitForAuthUser(timeoutMs = 5000) {
    const auth = getAuth();
    if (!auth) return null;
    if (auth.currentUser) return auth.currentUser;
    return new Promise((resolve) => {
        let done = false;
        let unsubscribe = null;
        const finish = (user) => {
            if (done) return;
            done = true;
            if (typeof unsubscribe === "function") unsubscribe();
            resolve(user || null);
        };
        const timer = setTimeout(() => finish(auth.currentUser || null), timeoutMs);
        unsubscribe = auth.onAuthStateChanged((user) => {
            clearTimeout(timer);
            finish(user || null);
        });
    });
}

async function getFreshAuthToken(opts = {}) {
    const { timeoutMs = 5000, forceRefresh = false } = opts || {};
    const user = await waitForAuthUser(timeoutMs);
    if (!user) return null;
    try {
        const token = await user.getIdToken(!!forceRefresh);
        if (token) localStorage.setItem("idToken", token);
        return token || null;
    } catch (e) {
        console.warn("getFreshAuthToken failed", e);
        return null;
    }
}

/* ============================
   MOBILE NAV (BURGER)
============================ */
function ensureMobileNavStyles() {
    if (document.getElementById("site-shell-style")) return;
    const link = document.createElement("link");
    link.id = "site-shell-style";
    link.rel = "stylesheet";
    link.href = "site-shell.css?v=20261030-1";
    document.head.appendChild(link);
}

function ensureNavOverlay() {
    let overlay = document.getElementById("nav-overlay");
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = "nav-overlay";
    document.body.appendChild(overlay);
    return overlay;
}

function bindMobileNav(nav) {
    const burger = nav.querySelector(".nav-burger");
    const drawer = nav.querySelector(".nav-drawer");
    const overlay = ensureNavOverlay();
    if (!burger || !drawer) return;

    const closeMenu = () => {
        document.body.classList.remove("nav-open");
        burger.setAttribute("aria-expanded", "false");
        drawer.setAttribute("aria-hidden", "true");
    };

    const toggleMenu = () => {
        const isOpen = document.body.classList.toggle("nav-open");
        burger.setAttribute("aria-expanded", String(isOpen));
        drawer.setAttribute("aria-hidden", String(!isOpen));
    };

    burger.onclick = toggleMenu;
    overlay.onclick = closeMenu;
    drawer.querySelectorAll("a").forEach(link => {
        link.addEventListener("click", closeMenu);
    });
    window.addEventListener("resize", () => {
        if (window.innerWidth > 1080) closeMenu();
    });
    closeMenu();
}

// A small glow follows the cursor along the header and its bottom edge.
function bindHeaderBeam(shell) {
    if (!shell || shell.__beamBound) return;
    shell.__beamBound = true;
    if (!shell.querySelector(".nav-beam")) {
        const beam = document.createElement("span");
        beam.className = "nav-beam";
        beam.setAttribute("aria-hidden", "true");
        shell.appendChild(beam);
    }
    shell.addEventListener("pointermove", (event) => {
        if (event.pointerType && event.pointerType !== "mouse") return;
        const rect = shell.getBoundingClientRect();
        shell.style.setProperty("--beam-x", `${Math.round(event.clientX - rect.left)}px`);
        shell.style.setProperty("--beam", "1");
    });
    shell.addEventListener("pointerleave", () => shell.style.setProperty("--beam", "0"));
}

// The header glass gets denser once the page is scrolled.
function bindHeaderScroll(shell) {
    if (!shell) return;
    const apply = () => shell.classList.toggle("is-scrolled", window.scrollY > 40);
    apply();
    if (window.__codebugHeaderScroll) return;
    window.__codebugHeaderScroll = true;
    let frame = 0;
    window.addEventListener("scroll", () => {
        if (frame) return;
        frame = requestAnimationFrame(() => {
            frame = 0;
            const el = document.querySelector(".cb-site-header");
            if (el) el.classList.toggle("is-scrolled", window.scrollY > 40);
        });
    }, { passive: true });
}

function bindAccountMenu(nav) {
    const wrap = nav.querySelector(".nav-profile-wrap");
    const button = nav.querySelector(".nav-profile");
    const menu = nav.querySelector(".nav-account-menu");
    if (!wrap || !button || !menu) return;

    const closeMenu = () => {
        wrap.classList.remove("menu-open");
        button.setAttribute("aria-expanded", "false");
    };

    const openMenu = () => {
        wrap.classList.add("menu-open");
        button.setAttribute("aria-expanded", "true");
    };

    const hoverCapable = !!(window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches);

    button.onclick = (event) => {
        event.preventDefault();
        event.stopPropagation();
        // With a mouse the menu is already open under the cursor, so a click opens the profile.
        if (hoverCapable) {
            window.location.href = "profile.html";
            return;
        }
        const isOpen = wrap.classList.toggle("menu-open");
        button.setAttribute("aria-expanded", String(isOpen));
    };

    // On a mouse the menu follows the pointer; a touch still needs a tap.
    if (hoverCapable) {
        let timer = 0;
        const later = (fn, ms) => {
            clearTimeout(timer);
            timer = setTimeout(fn, ms);
        };
        wrap.addEventListener("pointerenter", (event) => {
            if (event.pointerType === "touch") return;
            later(openMenu, 70);
        });
        wrap.addEventListener("pointerleave", (event) => {
            if (event.pointerType === "touch") return;
            later(closeMenu, 180);
        });
        wrap.addEventListener("pointerdown", () => clearTimeout(timer));
    }

    wrap.addEventListener("focusin", openMenu);
    wrap.addEventListener("focusout", () => {
        setTimeout(() => {
            if (!wrap.contains(document.activeElement)) closeMenu();
        }, 0);
    });

    menu.querySelectorAll("a, button").forEach((item) => {
        item.addEventListener("click", closeMenu);
    });

    if (!window.__codebugAccountMenuBound) {
        window.__codebugAccountMenuBound = true;
        document.addEventListener("click", (event) => {
            document.querySelectorAll("#nav-links .nav-profile-wrap.menu-open").forEach((openWrap) => {
                if (!openWrap.contains(event.target)) {
                    openWrap.classList.remove("menu-open");
                    const openButton = openWrap.querySelector(".nav-profile");
                    if (openButton) openButton.setAttribute("aria-expanded", "false");
                }
            });
        });
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") return;
            document.querySelectorAll("#nav-links .nav-profile-wrap.menu-open").forEach((openWrap) => {
                openWrap.classList.remove("menu-open");
                const openButton = openWrap.querySelector(".nav-profile");
                if (openButton) openButton.setAttribute("aria-expanded", "false");
            });
        });
    }

    closeMenu();
}

/* ============================
   ADMIN ACCESS
============================ */
async function checkAdminAccess() {
    const user = getUser();
    if (!user) return false;
    const dbRef = getDb();
    if (!dbRef) return false;
    try {
        const snap = await dbRef.ref("admins/" + user).get();
        return snap.exists();
    } catch (err) {
        console.warn("Admin check failed", err);
        return false;
    }
}


/* ============================
   NAVIGATION BAR
============================ */
function buildCodeBugBrandHtml(text) {
    const raw = String(text || "CodeBug").trim() || "CodeBug";
    const suffix = raw.replace(/^CodeBug/i, "").trim();
    const suffixHtml = suffix
        ? ` <span class="brand-suffix">${suffix.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;")}</span>`
        : "";
    return `<span class="brand-code">Code</span><span class="brand-bug">Bug</span>${suffixHtml}`;
}

function runLowPriority(task) {
    if (typeof task !== "function") return;
    if (typeof requestIdleCallback === "function") {
        requestIdleCallback(() => task(), { timeout: 1800 });
    } else {
        setTimeout(task, 600);
    }
}

// Task tags come from the task packages in English; show them in Russian everywhere.
const TAG_RU = {
    "idea": "идея",
    "interactive": "интерактив",
    "overflow": "переполнение",
    "math": "математика",
    "hash table": "хеш-таблицы",
    "binary search": "бинарный поиск",
    "prefix sums": "префиксные суммы",
    "time limit": "медленное решение",
    "modular exponentiation": "быстрое возведение в степень",
    "modulo": "остатки по модулю",
    "xor": "xor",
    "dijkstra": "алгоритм Дейкстры",
    "subgroups": "подгруппы",
    "permutation": "перестановки",
    "queries": "запросы",
    "two pointers": "два указателя",
    "constructive": "конструктив",
    "integer sqrt": "целый корень",
    "precision": "точность вычислений",
    "input": "ввод данных",
    "implementation": "реализация",
    "multiset": "multiset",
    "counting": "подсчёт",
    "bruteforce": "перебор",
    "brute force": "перебор",
    "dynamic programming": "динамика",
    "dp": "динамика",
    "graphs": "графы",
    "graph": "графы",
    "strings": "строки",
    "string": "строки",
    "arrays": "массивы",
    "array": "массивы",
    "sorting": "сортировка",
    "greedy": "жадность",
    "tree": "деревья",
    "trees": "деревья",
    "divide and conquer optimization": "оптимизация «разделяй и властвуй»",
    "dsu rollback": "СНМ с откатами",
    "dynamic connectivity": "динамическая связность",
    "factorization": "разложение на множители",
    "fenwick tree": "дерево Фенвика",
    "gcd": "НОД",
    "geometry": "геометрия",
    "invariant": "инвариант",
    "lazy propagation": "отложенные операции",
    "monotonic deque": "монотонная очередь",
    "mst": "минимальный остов",
    "multitest": "мультитест",
    "prefix function": "префикс-функция",
    "rerooting": "перевешивание корня",
    "segment tree": "дерево отрезков",
    "set": "множество",
    "suffix automaton": "суффиксный автомат"
};

function codebugTagRu(tag) {
    const raw = String(tag || "").trim();
    const key = raw.toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
    return TAG_RU[key] || raw;
}

// codebugPlural(5, "задача", "задачи", "задач") -> "5 задач"
function codebugPlural(n, one, few, many) {
    const abs = Math.abs(Number(n) || 0);
    const m10 = abs % 10, m100 = abs % 100;
    const word = m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? few : many;
    return `${n} ${word}`;
}

const NAV_ITEMS = [
    { href: "index.html", label: "Главное", aliases: ["", "index.html"] },
    { href: "train.html", label: "Тренировка", aliases: ["train.html", "problem.html"] },
    { href: "contests.html", label: "Соревнования", aliases: ["contests.html", "contest.html"] },
    { href: "rating.html", label: "Рейтинг", aliases: ["rating.html"] },
    { href: "donate.html", label: "Подписка", aliases: ["donate.html"] },
    { href: "faq.html", label: "Помощь", aliases: ["faq.html"] }
];

function getCurrentPageName() {
    const file = window.location.pathname.split("/").pop() || "index.html";
    return file === "/" ? "index.html" : file;
}

function getActiveNavHref() {
    const page = getCurrentPageName();
    const item = NAV_ITEMS.find((navItem) => navItem.aliases.includes(page));
    return item ? item.href : "";
}

function buildNavLinksHtml() {
    const activeHref = getActiveNavHref();
    return NAV_ITEMS.map((item) => {
        const active = item.href === activeHref ? " active" : "";
        return `<a href="${item.href}" class="${active.trim()}">${item.label}</a>`;
    }).join("");
}

function getProfileInitial(login) {
    const clean = String(login || "U").trim();
    return escapeInlineHtml(clean.slice(0, 1) || "U");
}

function normalizeSafeImageUrl(url) {
    const raw = String(url || "").trim();
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw) || raw.startsWith("/")) return raw;
    return "";
}

function getSubscriptionLabel(level) {
    if (level === "pro_plus") return "PRO+";
    if (level === "pro") return "PRO";
    return "FREE";
}

const NAVBAR_IDENTITY_CACHE_KEY = "codebug.navbarIdentity.v1";
const NAVBAR_IDENTITY_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

function normalizeSubscriptionForUi(value) {
    if (!value || typeof value !== "object") return null;
    return {
        tier: String(value.tier || "").toLowerCase(),
        status: String(value.status || "").toLowerCase(),
        expiresAt: value.expiresAt || null,
        graceUntil: value.graceUntil || value.paymentGraceUntil || null,
        daysLeft: value.daysLeft ?? null,
        graceDaysLeft: value.graceDaysLeft ?? null,
        paymentWarning: value.paymentWarning || null,
        features: (value.features && typeof value.features === "object") ? value.features : {},
        visuals: (value.visuals && typeof value.visuals === "object") ? value.visuals : {}
    };
}

function readNavbarIdentityCache(login) {
    try {
        const cached = JSON.parse(localStorage.getItem(NAVBAR_IDENTITY_CACHE_KEY) || "null");
        if (!cached || cached.login !== login) return null;
        const savedAt = Number(cached.savedAt || 0);
        if (!savedAt || Date.now() - savedAt > NAVBAR_IDENTITY_CACHE_MAX_AGE_MS) {
            localStorage.removeItem(NAVBAR_IDENTITY_CACHE_KEY);
            return null;
        }
        return {
            subscription: normalizeSubscriptionForUi(cached.subscription),
            exp: Number(cached.exp || 0),
            avatarUrl: normalizeSafeImageUrl(cached.avatarUrl || "")
        };
    } catch (_) {
        localStorage.removeItem(NAVBAR_IDENTITY_CACHE_KEY);
        return null;
    }
}

function writeNavbarIdentityCache(login, identity) {
    if (!login || !identity || typeof identity !== "object") return;
    try {
        localStorage.setItem(NAVBAR_IDENTITY_CACHE_KEY, JSON.stringify({
            login,
            savedAt: Date.now(),
            subscription: normalizeSubscriptionForUi(identity.subscription),
            exp: Number(identity.exp || 0),
            avatarUrl: normalizeSafeImageUrl(identity.avatarUrl || "")
        }));
    } catch (_) {}
}

function clearNavbarIdentityCache(login) {
    try {
        const cached = JSON.parse(localStorage.getItem(NAVBAR_IDENTITY_CACHE_KEY) || "null");
        if (!login || !cached || cached.login === login) {
            localStorage.removeItem(NAVBAR_IDENTITY_CACHE_KEY);
        }
    } catch (_) {
        localStorage.removeItem(NAVBAR_IDENTITY_CACHE_KEY);
    }
}

function buildBellIconHtml() {
    return codebugIcon("bell", { size: 22 });
}

function buildAccountHtml(user) {
    if (!user) {
        return `<a class="nav-auth-link" href="auth.html">Войти / Регистрация</a>`;
    }

    const safeUser = escapeInlineHtml(user);
    const initial = getProfileInitial(user);
    return `
        <button class="nav-notification" type="button" aria-label="Уведомления" title="Уведомления">
            ${buildBellIconHtml()}
            <span class="nav-notification-dot" aria-hidden="true"></span>
        </button>
        <div class="nav-profile-wrap">
            <button class="nav-profile" type="button" aria-haspopup="menu" aria-expanded="false">
                <span class="nav-avatar" data-initial="${initial}">${initial}</span>
                <span class="nav-profile-text">
                    <span class="nav-profile-name">${safeUser}</span>
                    <span class="nav-profile-tier">FREE</span>
                </span>
            </button>
            <div class="nav-account-menu" role="menu">
                <a href="profile.html" role="menuitem">Профиль</a>
                <a href="profile.html#settings" role="menuitem">Настройки</a>
                <div class="nav-menu-separator" aria-hidden="true"></div>
                <button class="nav-menu-danger" type="button" role="menuitem" onclick="logout()">Выйти</button>
            </div>
        </div>
    `;
}

function buildDrawerAccountHtml(user) {
    if (!user) return `<a href="auth.html">Войти / Регистрация</a>`;
    return `
        <a href="profile.html">Профиль</a>
        <a href="profile.html#settings">Настройки</a>
        <a href="#" onclick="logout(); return false;">Выйти</a>
    `;
}

function updateNavbar() {
    const nav = document.getElementById("nav-links");
    if (!nav) return;

    const header = nav.closest("header");
    const topNavInner = nav.closest(".top-nav-inner");
    const shell = header || topNavInner;
    if (shell) shell.classList.add("cb-site-header");

    const logos = document.querySelectorAll(".logo");
    logos.forEach((logo) => {
        if (logo.querySelector("a")) return;
        logo.innerHTML = `<a href="index.html" style="color:inherit;text-decoration:none;">${buildCodeBugBrandHtml("CodeBug")}</a>`;
    });

    const user = getUser();
    ensureMobileNavStyles();

    const commonLinks = buildNavLinksHtml();
    const accountLinks = buildAccountHtml(user);
    const drawerLinks = `${commonLinks}${buildDrawerAccountHtml(user)}`;

    nav.innerHTML = `
        <div class="nav-shell">
            <div class="nav-links nav-primary">${commonLinks}</div>
            <div class="nav-links nav-account">${accountLinks}</div>
            <button class="nav-burger" type="button" aria-label="Меню" aria-expanded="false">${codebugIcon("menu", { size: 22 })}</button>
        </div>
        <div class="nav-drawer" aria-hidden="true">${drawerLinks}</div>
    `;

    const cachedIdentity = readNavbarIdentityCache(user);
    if (cachedIdentity) applyNavbarIdentity(user, cachedIdentity);

    bindMobileNav(nav);
    bindAccountMenu(nav);
    bindHeaderBeam(shell);
    bindHeaderScroll(shell);
    runLowPriority(startKeepAlive);
    runLowPriority(() => applyProBrandingToNavbar(user).catch(() => {}));
    runLowPriority(() => applyNavbarNotifications(user).catch(() => {}));
}

async function getUserSubscription(login) {
    if (!login) return null;
    try {
        const data = await CodeBugData.profile(login);
        const val = data.subscription || null;
        return normalizeSubscriptionForUi(val);
    } catch (err) {
        console.warn("getUserSubscription failed", err);
        return null;
    }
}

function getSubscriptionLevel(sub) {
    if (!sub) return "free";
    const status = String(sub.status || "").toLowerCase();
    if (!["active", "grace"].includes(status)) return "free";
    const now = Date.now();
    const expiresAt = Number(sub.expiresAt || 0);
    const graceUntil = Number(sub.graceUntil || 0);
    if (status === "active" && expiresAt && expiresAt < now && (!graceUntil || graceUntil < now)) return "free";
    if (status === "grace" && graceUntil && graceUntil < now) return "free";
    const tier = String(sub.tier || "").toLowerCase();
    if (tier === "creator_dev") return "pro_plus";
    if (tier === "pro_plus") return "pro_plus";
    if (tier === "pro") return "pro";
    return "free";
}

function getRankNickColorByExp(exp) {
    const maxExp = 2000;
    const progress = Math.max(0, Math.min(1, Number(exp || 0) / maxExp));
    const lightness = Math.round(72 - progress * 36);
    return `hsl(145 58% ${lightness}%)`;
}

function hasSubscriptionAtLeast(sub, minLevel) {
    const rank = { free: 0, pro: 1, pro_plus: 2 };
    return (rank[getSubscriptionLevel(sub)] || 0) >= (rank[minLevel] || 0);
}

const PRO_NICK_SOLID_COLORS = [
    "#60a5fa", "#38bdf8", "#a78bfa", "#22d3ee", "#34d399",
    "#f472b6", "#f59e0b", "#ef4444", "#14b8a6", "#8b5cf6"
];
const PRO_PLUS_NICK_THEMES = [
    "grad_ocean", "grad_sunset", "grad_candy", "grad_aurora",
    "nutella", "rainbow", "fire_ice", "matrix", "blood_ink"
];

function getAllowedNickThemesForLevel(level) {
    const base = [...PRO_NICK_SOLID_COLORS];
    if (level === "pro_plus") base.push(...PRO_PLUS_NICK_THEMES);
    return base;
}

function getSubscriptionNickTheme(sub) {
    const level = getSubscriptionLevel(sub);
    const allowed = new Set(getAllowedNickThemesForLevel(level).map((x) => String(x).toLowerCase()));
    const raw = String(sub?.visuals?.nickColor || "").trim().toLowerCase();
    if (allowed.has(raw)) return raw;
    return PRO_NICK_SOLID_COLORS[0];
}

function getSubscriptionNickColor(sub) {
    const theme = getSubscriptionNickTheme(sub);
    if (theme.startsWith("#")) return theme;
    return PRO_NICK_SOLID_COLORS[0];
}

function escapeInlineHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function buildStyledNickHtml(login, sub, fallbackColor) {
    const safe = escapeInlineHtml(login);
    const level = getSubscriptionLevel(sub);
    if (level === "free") return `<span style="color:#FFFFFF">${safe}</span>`;
    const theme = getSubscriptionNickTheme(sub);
    if (theme.startsWith("#")) return `<span style="color:${theme}">${safe}</span>`;
    if (theme === "grad_ocean") {
        return `<span style="background:linear-gradient(90deg,#38bdf8,#22d3ee,#60a5fa);-webkit-background-clip:text;background-clip:text;color:transparent;">${safe}</span>`;
    }
    if (theme === "grad_sunset") {
        return `<span style="background:linear-gradient(90deg,#fb7185,#f97316,#facc15);-webkit-background-clip:text;background-clip:text;color:transparent;">${safe}</span>`;
    }
    if (theme === "grad_candy") {
        return `<span style="background:linear-gradient(90deg,#f472b6,#a78bfa,#60a5fa);-webkit-background-clip:text;background-clip:text;color:transparent;">${safe}</span>`;
    }
    if (theme === "grad_aurora") {
        return `<span style="background:linear-gradient(90deg,#22c55e,#06b6d4,#8b5cf6);-webkit-background-clip:text;background-clip:text;color:transparent;">${safe}</span>`;
    }
    if (theme === "nutella") {
        const letters = Array.from(safe);
        return letters.map((ch, i) => `<span style="color:${i === 0 ? "#ffffff" : "#ef4444"}">${ch}</span>`).join("");
    }
    if (theme === "rainbow") {
        const colors = ["#ef4444", "#f97316", "#facc15", "#22c55e", "#06b6d4", "#8b5cf6", "#f472b6"];
        return Array.from(safe).map((ch, i) => `<span style="color:${colors[i % colors.length]}">${ch}</span>`).join("");
    }
    if (theme === "fire_ice") {
        return `<span style="background:linear-gradient(90deg,#ef4444,#f97316,#38bdf8,#2563eb);-webkit-background-clip:text;background-clip:text;color:transparent;">${safe}</span>`;
    }
    if (theme === "matrix") {
        return `<span style="color:#22c55e;text-shadow:0 0 8px rgba(34,197,94,.28);">${safe}</span>`;
    }
    if (theme === "blood_ink") {
        return `<span style="color:#0b0b0b;text-shadow:1px 1px 0 #7f0f16,2px 2px 0 rgba(127,15,22,.75),0 0 12px rgba(127,15,22,.35);">${safe}</span>`;
    }
    return `<span style="color:#FFFFFF">${safe}</span>`;
}

function isProSubscription(sub) {
    return hasSubscriptionAtLeast(sub, "pro");
}

async function applyProBrandingToNavbar(login) {
    if (!login) return;
    const base = window.TASKS_API_BASE || window.CODEBUG_API_BASE || "https://codebug.onrender.com";
    let sub = null;
    let exp = 0;
    let avatarUrl = "";
    let hasFreshIdentity = false;

    try {
        const profile = await CodeBugData.profile(login);
        sub = normalizeSubscriptionForUi(profile.subscription);
        avatarUrl = normalizeSafeImageUrl(profile.avatarUrl || "");
        exp = Number(profile.stats?.exp || 0);
        hasFreshIdentity = true;
    } catch (_) {}

    if (!hasFreshIdentity) sub = await getUserSubscription(login);
    try {
        if (!hasFreshIdentity) {
            const profileSnap = await firebase.database().ref("publicProfiles/" + login).get();
            if (profileSnap.exists()) {
                const profile = profileSnap.val() || {};
                avatarUrl = normalizeSafeImageUrl(profile.avatarUrl || "");
                exp = Number(profile?.stats?.exp || 0);
                hasFreshIdentity = true;
            }
        }
    } catch (_) {}
    if (!avatarUrl) {
        try {
            const avatarSnap = await firebase.database().ref("users/" + login + "/avatarUrl").get();
            if (avatarSnap.exists()) avatarUrl = normalizeSafeImageUrl(avatarSnap.val());
        } catch (_) {}
    }
    if (!exp) {
        try {
            const userSnap = await firebase.database().ref("users/" + login + "/stats/exp").get();
            if (userSnap.exists()) exp = Number(userSnap.val() || 0);
        } catch (_) {}
    }

    applyNavbarIdentity(login, { subscription: sub, exp, avatarUrl });
    if (hasFreshIdentity) writeNavbarIdentityCache(login, { subscription: sub, exp, avatarUrl });
}

function applyNavbarIdentity(login, identity) {
    if (!login || !identity) return;
    const sub = normalizeSubscriptionForUi(identity.subscription);
    const exp = Number(identity.exp || 0);
    const avatarUrl = normalizeSafeImageUrl(identity.avatarUrl || "");
    const level = getSubscriptionLevel(sub);
    const isPro = level !== "free";
    const nickColor = isPro ? getSubscriptionNickColor(sub) : getRankNickColorByExp(exp);
    const navProfileName = document.querySelector("#nav-links .nav-profile-name");
    const navProfileTier = document.querySelector("#nav-links .nav-profile-tier");
    const navAvatar = document.querySelector("#nav-links .nav-avatar");

    if (navProfileName) {
        navProfileName.innerHTML = buildStyledNickHtml(login, sub, nickColor);
        navProfileName.style.fontWeight = "750";
    }
    if (navProfileTier) {
        navProfileTier.textContent = getSubscriptionLabel(level);
        navProfileTier.classList.toggle("is-pro", isPro);
    }
    if (navAvatar) {
        if (avatarUrl) {
            const optimized = typeof getOptimizedAvatarUrl === "function" ? getOptimizedAvatarUrl(avatarUrl) : avatarUrl;
            navAvatar.innerHTML = `<img src="${escapeInlineHtml(optimized)}" alt="">`;
        } else {
            navAvatar.textContent = getProfileInitial(login);
        }
    }
}

function notificationValueHasUnread(value) {
    if (!value) return false;
    if (Array.isArray(value)) return value.some(notificationValueHasUnread);
    if (typeof value !== "object") return false;
    if (value.unread === true || value.read === false || value.seen === false) return true;
    if (value.readAt === null || value.seenAt === null) return true;
    return Object.values(value).some((item) => {
        if (!item || typeof item !== "object") return false;
        return item.unread === true || item.read === false || item.seen === false || item.readAt === null || item.seenAt === null;
    });
}

async function applyNavbarNotifications(login) {
    const button = document.querySelector("#nav-links .nav-notification");
    if (!button || !login || !window.firebase) return;
    let hasUnread = false;
    const paths = [`notifications/${login}`, `userNotifications/${login}`];
    for (const path of paths) {
        try {
            const snap = await firebase.database().ref(path).limitToLast(20).get();
            if (snap.exists() && notificationValueHasUnread(snap.val())) {
                hasUnread = true;
                break;
            }
        } catch (_) {}
    }
    button.classList.toggle("has-unread", hasUnread);
}

/* ============================
   KEEP ALIVE (Render)
============================ */
function startKeepAlive() {
    if (window.__keepAliveTimer) return;
    const base = window.TASKS_API_BASE || "";
    if (!base) return;
    const interval = 9 * 60 * 1000; // 9 minutes
    const ping = () => {
        fetch(`${base}/ping`, { method: "GET", cache: "no-store" }).catch(() => {});
    };
    ping();
    window.__keepAliveTimer = setInterval(ping, interval);
}

function ensureGlobalFooter() {
    if (typeof document === "undefined") return;
    if (document.getElementById("global-legal-footer")) return;

    const footer = document.createElement("footer");
    footer.id = "global-legal-footer";
    footer.innerHTML = `
        <div class="cb-legal-footer-inner">
            <a class="cb-legal-btn" href="/privacy.html">Политика конфиденциальности</a>
            <a class="cb-legal-btn" href="/terms.html">Пользовательское соглашение</a>
            <a class="cb-legal-btn" href="https://t.me/afony_l" target="_blank" rel="noopener">Поддержка: @afony_l</a>
            <a class="cb-legal-btn" href="mailto:support@codebug.online">support@codebug.online</a>
        </div>
    `;

    ensureMobileNavStyles();
    document.body.classList.add("cb-footer-layout");
    document.body.appendChild(footer);
}

/* ============================
   PRESENCE (ONLINE / LAST SEEN)
============================ */
function startPresence() {
    const user = getUser();
    if (!user || !window.firebase) return;

    const ref = firebase.database().ref("users/" + user + "/presence");
    const now = Date.now();

    ref.update({
        online: true,
        lastSeen: now
    });

    ref.onDisconnect().update({
        online: false,
        lastSeen: firebase.database.ServerValue.TIMESTAMP
    });

    if (!window.__presenceTimer) {
        window.__presenceTimer = setInterval(() => {
            ref.update({
                online: true,
                lastSeen: Date.now()
            });
        }, 30000);
    }
}

/* ============================
   ERROR HELPERS
============================ */
function showError(id, text) {
    const elem = document.getElementById(id);
    if (elem) elem.innerText = text;
}

function clearErrors() {
    showError("login-error", "");
    showError("reg-error", "");
    showError("verify-error", "");
    showError("google-error", "");
}


/* ============================
   FIREBASE AUTH HELPERS
============================ */
var EMAIL_RETRY_COOLDOWN_MS = 60 * 1000;
var lastVerificationSentAt = 0;
var PENDING_REG_KEY = "pendingRegistration";
let registrationRecoveryInProgress = false;
var RECAPTCHA_PLACEHOLDER_KEY = "PASTE_RECAPTCHA_SITE_KEY_HERE";
var captchaWidgetId = null;
var captchaToken = "";
window.__captchaReady = !!window.__captchaReady;

function getAuth() {
    if (!window.firebase || typeof firebase.auth !== "function") return null;
    try {
        const auth = firebase.auth();
        // Firebase picks the language of its emails (verification, password reset)
        // from this value; without it every letter goes out in English.
        if (auth.languageCode !== "ru") auth.languageCode = "ru";
        return auth;
    } catch (_) {
        return null;
    }
}

function setUid(uid) {
    if (!uid) {
        localStorage.removeItem("uid");
        return;
    }
    localStorage.setItem("uid", uid);
}

function getUid() {
    return localStorage.getItem("uid");
}

function normalizeEmail(email) {
    return String(email || "").trim().toLowerCase();
}

function emailKey(email) {
    return normalizeEmail(email).replace(/\./g, ",");
}

function getPendingRegistration() {
    try {
        const raw = localStorage.getItem(PENDING_REG_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || !parsed.email || !parsed.login) return null;
        return {
            login: String(parsed.login),
            email: normalizeEmail(parsed.email)
        };
    } catch (_) {
        return null;
    }
}

function setPendingRegistration(data) {
    if (!data || !data.login || !data.email) {
        localStorage.removeItem(PENDING_REG_KEY);
        return;
    }
    localStorage.setItem(PENDING_REG_KEY, JSON.stringify({
        login: String(data.login),
        email: normalizeEmail(data.email)
    }));
}

function clearPendingRegistration() {
    localStorage.removeItem(PENDING_REG_KEY);
}

function isRegistrationLocked() {
    return !!getPendingRegistration();
}

function showVerifyScreen(emailText, infoText = "") {
    const loginScreen = document.getElementById("screen-login");
    const regScreen = document.getElementById("screen-register");
    const verifyScreen = document.getElementById("screen-verify");
    if (!verifyScreen) return;

    if (loginScreen) loginScreen.style.display = "none";
    if (regScreen) regScreen.style.display = "none";
    verifyScreen.style.display = "block";

    const label = document.getElementById("verify-email-label");
    if (label) label.innerText = emailText || "указанный email";
    showError("verify-error", infoText);
}

function redirectToAuthForVerification() {
    const next = encodeURIComponent(window.location.pathname.split("/").pop() || "index.html");
    window.location.href = `auth.html?verify=1&next=${next}`;
}

window.addEventListener("beforeunload", (event) => {
    if (!isAuthPage()) return;
    if (!isRegistrationLocked()) return;
    event.preventDefault();
    event.returnValue = "";
});

function resetTurnstileWidget() {
    captchaToken = "";
    window.__captchaReady = false;
    setRegisterButtonEnabled(false, "Пройди капчу");
    if (window.grecaptcha && captchaWidgetId !== null) {
        try {
            window.grecaptcha.reset(captchaWidgetId);
        } catch (_) {}
    }
}

function setRegisterButtonEnabled(enabled, reason = "") {
    const btn = document.getElementById("reg-submit-btn");
    if (!btn) return;
    btn.disabled = !enabled;
    if (reason) {
        btn.title = reason;
    } else {
        btn.removeAttribute("title");
    }
}

function getTurnstileSiteKey() {
    const key = String(window.RECAPTCHA_SITE_KEY || "").trim();
    const placeholder = (typeof RECAPTCHA_PLACEHOLDER_KEY === "string" && RECAPTCHA_PLACEHOLDER_KEY)
        ? RECAPTCHA_PLACEHOLDER_KEY
        : "PASTE_RECAPTCHA_SITE_KEY_HERE";
    if (!key || key === placeholder) return "";
    return key;
}

function renderCaptchaWidget() {
    const host = document.getElementById("turnstile-box");
    if (!host) return;
    window.__captchaReady = false;
    setRegisterButtonEnabled(false, "Капча загружается");

    const siteKey = getTurnstileSiteKey();
    if (!siteKey) {
        host.style.borderColor = "rgba(194, 64, 64, 0.9)";
        host.innerHTML = `<span style="font-size:12px;color:#c24040;">Капча не настроена: отсутствует reCAPTCHA site key</span>`;
        showError("reg-error", "Регистрация недоступна: капча не настроена");
        setRegisterButtonEnabled(false, "Капча не настроена");
        return;
    }

    if (!window.grecaptcha || typeof window.grecaptcha.render !== "function") {
        setTimeout(renderCaptchaWidget, 250);
        return;
    }

    if (captchaWidgetId !== null) {
        resetTurnstileWidget();
        return;
    }

    host.style.borderColor = "rgba(255, 255, 255, 0.08)";
    host.innerHTML = "";
    captchaWidgetId = window.grecaptcha.render(host, {
        sitekey: siteKey,
        theme: "dark",
        callback: (token) => {
            captchaToken = token || "";
            window.__captchaReady = !!captchaToken;
            setRegisterButtonEnabled(window.__captchaReady, window.__captchaReady ? "" : "Пройди капчу");
            if (window.__captchaReady) showError("reg-error", "");
        },
        "expired-callback": () => {
            captchaToken = "";
            window.__captchaReady = false;
            setRegisterButtonEnabled(false, "Капча устарела");
        },
        "error-callback": () => {
            captchaToken = "";
            window.__captchaReady = false;
            setRegisterButtonEnabled(false, "Ошибка капчи");
            showError("reg-error", "Ошибка капчи. Обнови страницу и попробуй снова.");
        }
    });
}

async function verifyCaptchaToken(token) {
    const base = window.TASKS_API_BASE || "";
    if (!base) return { ok: false, error: "Сервис капчи недоступен" };

    const toMessage = (code) => {
        const map = {
            captcha_not_configured: "Капча на сервере не настроена",
            captcha_token_required: "Подтверди капчу",
            captcha_timeout_or_duplicate: "Капча устарела. Пройди ее заново",
            captcha_invalid_input_response: "Неверный токен капчи. Пройди заново",
            captcha_verify_unavailable: "Сервис проверки капчи недоступен",
            captcha_invalid: "Капча не пройдена"
        };
        return map[code] || "Капча не пройдена";
    };

    try {
        const response = await fetch(`${base}/auth/verify-captcha`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token })
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) {
            return { ok: false, error: toMessage(payload.error) };
        }
        return { ok: true };
    } catch (_) {
        return { ok: false, error: "Не удалось проверить капчу" };
    }
}

function isLoginValid(login) {
    return /^[a-zA-Z0-9_]{3,16}$/.test(login);
}

async function resolveLoginByUidOrEmail(uid, email) {
    if (uid) {
        const mapSnap = await db.ref("userAuthMap/" + uid).get();
        if (mapSnap.exists()) return mapSnap.val();
    }
    return null;
}

async function resolveEmailByIdentity(identity) {
    const raw = String(identity || "").trim();
    return raw.includes("@") ? normalizeEmail(raw) : null;
}

async function ensureUserProfile(login, userAuth) {
    // Email verification changes the claims in the ID token. `reload()` updates
    // userAuth.emailVerified, but Firebase may still return the cached token
    // issued before verification unless a refresh is forced. The backend checks
    // the token claim, so using the stale token made fresh registrations fail
    // with EMAIL_NOT_VERIFIED at the final profile-sync step.
    const token = await userAuth.getIdToken(true);
    if (token) localStorage.setItem("idToken", token);
    const base = window.getTasksApiBase
        ? window.getTasksApiBase()
        : (window.TASKS_API_BASE || "https://codebug.onrender.com");
    const response = await fetch(`${base}/auth/finalize-profile`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ login })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload.login) {
        throw new Error(payload.code || payload.error || "PROFILE_FINALIZE_FAILED");
    }
    return payload.login;
}

async function loginUser(identity, pass) {
    const auth = getAuth();
    if (!auth) return { ok: false, error: "Сервис входа временно недоступен" };

    let cred;
    let loginHint = null;
    try {
        const rawIdentity = String(identity || "").trim();
        if (rawIdentity.includes("@")) {
            cred = await auth.signInWithEmailAndPassword(normalizeEmail(rawIdentity), pass);
        } else {
            const base = window.getTasksApiBase
                ? window.getTasksApiBase()
                : (window.TASKS_API_BASE || "https://codebug.onrender.com");
            const response = await fetch(`${base}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ identity: rawIdentity, password: pass })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.customToken) {
                const error = new Error("invalid credentials");
                error.code = response.status === 429 ? "auth/too-many-requests" : "auth/invalid-credential";
                throw error;
            }
            loginHint = String(payload.login || rawIdentity).trim() || null;
            cred = await auth.signInWithCustomToken(payload.customToken);
        }
    } catch (err) {
        const code = err?.code || "";
        console.warn("Login failed", code || err);
        if ([
            "auth/user-not-found",
            "auth/wrong-password",
            "auth/invalid-email",
            "auth/invalid-credential",
            "auth/invalid-login-credentials"
        ].includes(code)) {
            return { ok: false, error: "Неправильный логин или пароль" };
        }
        if (code === "auth/too-many-requests") {
            return { ok: false, error: "Слишком много попыток. Попробуй позже" };
        }
        return { ok: false, error: "Не удалось войти. Попробуй ещё раз" };
    }

    await cred.user.reload();
    const userAuth = auth.currentUser || cred.user;
    if (!userAuth.emailVerified) {
        return { ok: false, needVerify: true, userAuth, error: "Подтверди email перед входом" };
    }

    return { ok: true, userAuth, loginHint };
}

/* ============================
   SIGN IN WITH GOOGLE
   Google accounts always carry a verified email, so they go through the same
   /auth/finalize-profile step as a verified email/password account. A first
   Google sign-in has no login yet: the visitor picks one on #screen-google.
============================ */
var googleSignInBusy = false;

function suggestLoginFromGoogle(userAuth) {
    const fromEmail = String(userAuth?.email || "").split("@")[0];
    const fromName = String(userAuth?.displayName || "");
    let base = (fromEmail || fromName).replace(/[^a-zA-Z0-9_]/g, "_").replace(/_+/g, "_").replace(/^_|_$/g, "");
    if (base.length > 16) base = base.slice(0, 16);
    if (base.length < 3) base = ("user_" + base + Math.floor(Math.random() * 1000)).slice(0, 16);
    return base;
}

function showAuthScreen(id) {
    ["screen-login", "screen-register", "screen-verify", "screen-google"].forEach((screenId) => {
        const el = document.getElementById(screenId);
        if (el) el.style.display = screenId === id ? "block" : "none";
    });
}

function googleErrorText(code) {
    if (code === "auth/popup-closed-by-user" || code === "auth/cancelled-popup-request") return "";
    if (code === "auth/operation-not-allowed") return "Вход через Google пока не включён. Войди по логину и паролю";
    if (code === "auth/unauthorized-domain") return "Вход через Google не разрешён для этого адреса сайта";
    if (code === "auth/account-exists-with-different-credential") return "Этот email уже зарегистрирован. Войди по логину и паролю";
    if (code === "auth/network-request-failed") return "Нет связи с Google. Проверь интернет и попробуй ещё раз";
    if (code === "auth/too-many-requests") return "Слишком много попыток. Попробуй позже";
    return "Не удалось войти через Google. Попробуй ещё раз";
}

async function handleGoogleUser(userAuth, errorBoxId) {
    let mapped = null;
    try {
        mapped = await resolveLoginByUidOrEmail(userAuth.uid, userAuth.email);
    } catch (err) {
        console.warn("Google login lookup failed", err);
    }
    if (mapped) {
        const finalized = await finalizeVerifiedAccount(userAuth, mapped);
        if (!finalized.ok) return showError(errorBoxId, finalized.error);
        const next = new URLSearchParams(window.location.search).get("next");
        window.location.href = safeNextTarget(next);
        return;
    }
    // First Google sign-in: ask for a login before creating the profile.
    const input = document.getElementById("google-login");
    const label = document.getElementById("google-email-label");
    if (label) label.innerText = normalizeEmail(userAuth.email) || "твой Google-аккаунт";
    if (input && !input.value) input.value = suggestLoginFromGoogle(userAuth);
    showAuthScreen("screen-google");
    if (input) {
        input.focus();
        input.dispatchEvent(new Event("input", { bubbles: true }));
    }
}

async function loginWithGoogle(errorBoxId = "login-error") {
    clearErrors();
    if (googleSignInBusy) return;
    const auth = getAuth();
    if (!auth || !firebase.auth.GoogleAuthProvider) return showError(errorBoxId, "Сервис входа временно недоступен");
    const provider = new firebase.auth.GoogleAuthProvider();
    provider.setCustomParameters({ prompt: "select_account" });
    // An abandoned email registration must not hand its login to this Google account.
    clearPendingRegistration();
    googleSignInBusy = true;
    try {
        const cred = await auth.signInWithPopup(provider);
        await handleGoogleUser(cred.user, errorBoxId);
    } catch (err) {
        const code = err?.code || "";
        if (code === "auth/popup-blocked" || code === "auth/operation-not-supported-in-this-environment") {
            // The browser refused the popup: continue in this tab instead.
            try {
                sessionStorage.setItem("googleRedirectBox", errorBoxId);
                await auth.signInWithRedirect(provider);
                return;
            } catch (redirectErr) {
                console.warn("Google redirect failed", redirectErr);
                showError(errorBoxId, googleErrorText(redirectErr?.code || ""));
                return;
            }
        }
        console.warn("Google sign-in failed", code || err);
        showError(errorBoxId, googleErrorText(code));
    } finally {
        googleSignInBusy = false;
    }
}

async function completeGoogleLogin() {
    clearErrors();
    const auth = getAuth();
    const userAuth = auth && auth.currentUser;
    if (!userAuth) {
        showAuthScreen("screen-login");
        return showError("login-error", "Сессия Google истекла. Войди через Google ещё раз");
    }
    const login = String(document.getElementById("google-login")?.value || "").trim();
    if (!isLoginValid(login)) return showError("google-error", "Логин: 3-16 символов, латиница/цифры/_");
    try {
        const taken = await db.ref("publicProfiles/" + login + "/login").get();
        if (taken.exists()) return showError("google-error", "Логин уже занят");
    } catch (err) {
        console.warn("Login availability check failed", err);
    }
    const finalized = await finalizeVerifiedAccount(userAuth, login);
    if (!finalized.ok) {
        const msg = /уже занят/.test(finalized.error) ? "Логин уже занят" : finalized.error;
        return showError("google-error", msg);
    }
    const next = new URLSearchParams(window.location.search).get("next");
    window.location.href = safeNextTarget(next);
}

async function cancelGoogleLogin() {
    clearErrors();
    const auth = getAuth();
    try {
        if (auth && auth.currentUser) await auth.signOut();
    } catch (err) {
        console.warn("Google sign-out failed", err);
    }
    clearSession();
    const input = document.getElementById("google-login");
    if (input) input.value = "";
    showAuthScreen("screen-login");
}

async function resumeGoogleRedirect() {
    const auth = getAuth();
    if (!auth || !isAuthPage() || typeof auth.getRedirectResult !== "function") return;
    const box = sessionStorage.getItem("googleRedirectBox");
    if (!box) return;
    sessionStorage.removeItem("googleRedirectBox");
    try {
        const result = await auth.getRedirectResult();
        if (result && result.user) await handleGoogleUser(result.user, box);
    } catch (err) {
        console.warn("Google redirect result failed", err?.code || err);
        showError(box, googleErrorText(err?.code || ""));
    }
}

async function sendVerificationWithCooldown(userAuth) {
    const now = Date.now();
    if (now - lastVerificationSentAt < EMAIL_RETRY_COOLDOWN_MS) {
        const left = Math.ceil((EMAIL_RETRY_COOLDOWN_MS - (now - lastVerificationSentAt)) / 1000);
        return { ok: false, error: `Подожди ${left} сек перед повторной отправкой` };
    }
    try {
        await userAuth.sendEmailVerification();
        lastVerificationSentAt = now;
        return { ok: true };
    } catch (err) {
        return { ok: false, error: "Не удалось отправить письмо: " + (err?.code || "unknown") };
    }
}

async function login() {
    clearErrors();
    const identity = document.getElementById("login-identity").value.trim();
    const pass = document.getElementById("login-pass").value.trim();

    if (!identity) return showError("login-error", "Укажи логин или email");
    if (!pass) return showError("login-error", "Укажи пароль");
    if (pass.length < 6) return showError("login-error", "Неправильный логин или пароль");

    let result;
    try {
        result = await loginUser(identity, pass);
    } catch (err) {
        console.warn("Login request failed", err);
        return showError("login-error", "Не удалось войти. Попробуй ещё раз");
    }
    if (!result.ok) {
        if (result.needVerify && result.userAuth) {
            const pendingLogin = await resolveLoginByUidOrEmail(result.userAuth.uid, result.userAuth.email) || String(identity);
            setPendingRegistration({ login: pendingLogin, email: normalizeEmail(result.userAuth.email) });
            const sent = await sendVerificationWithCooldown(result.userAuth);
            if (!sent.ok) {
                showVerifyScreen(normalizeEmail(result.userAuth.email), `${result.error}. ${sent.error}`);
                return;
            }
            showVerifyScreen(normalizeEmail(result.userAuth.email), "Email не подтвержден. Отправили новую ссылку.");
            return;
        }
        return showError("login-error", result.error);
    }

    let finalized;
    try {
        finalized = await finalizeVerifiedAccount(result.userAuth, result.loginHint);
    } catch (err) {
        console.warn("Login profile sync failed", err);
        return showError("login-error", "Не удалось войти. Попробуй ещё раз");
    }
    if (!finalized.ok) return showError("login-error", finalized.error);

    const next = new URLSearchParams(window.location.search).get("next");
    window.location.href = safeNextTarget(next);
}

async function forgotPassword() {
    clearErrors();
    const identity = document.getElementById("login-identity").value.trim();
    if (!identity) return showError("login-error", "Укажи логин или email для восстановления");

    try {
        const base = window.getTasksApiBase
            ? window.getTasksApiBase()
            : (window.TASKS_API_BASE || "https://codebug.onrender.com");
        const response = await fetch(`${base}/auth/password-reset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ identity })
        });
        if (!response.ok) {
            const error = new Error("password reset failed");
            error.code = response.status === 429 ? "auth/too-many-requests" : "auth/service-unavailable";
            throw error;
        }
    } catch (err) {
        const code = err?.code || "";
        if (code === "auth/invalid-email") return showError("login-error", "Некорректный email");
        if (code === "auth/user-not-found") return showError("login-error", "Пользователь не найден");
        if (code === "auth/too-many-requests") return showError("login-error", "Слишком много попыток, попробуй позже");
        return showError("login-error", "Не удалось отправить письмо: " + code);
    }

    showError("login-error", "Письмо для восстановления пароля отправлено");
}

async function registerUser(login, email, pass) {
    const auth = getAuth();
    if (!auth) return { ok: false, error: "Firebase Auth не инициализирован" };

    const snap = await db.ref("publicProfiles/" + login + "/login").get();
    if (snap.exists()) return { ok: false, error: "Логин уже занят" };

    const e = normalizeEmail(email);

    let cred;
    try {
        cred = await auth.createUserWithEmailAndPassword(e, pass);
    } catch (err) {
        const code = err?.code || "";
        if (code === "auth/email-already-in-use") {
            // Older interrupted registrations can leave a Firebase Auth user
            // without userAuthMap/users profile records. If the password proves
            // ownership, let that user finish registration instead of trapping
            // them forever behind "email already in use" / "login not found".
            registrationRecoveryInProgress = true;
            try {
                cred = await auth.signInWithEmailAndPassword(e, pass);
                const existingUser = cred.user;
                await existingUser.reload();
                const mappedLogin = await resolveLoginByUidOrEmail(existingUser.uid, existingUser.email);
                if (mappedLogin) {
                    await auth.signOut();
                    return { ok: false, error: "Этот email уже занят. Войди в существующий аккаунт" };
                }

                setPendingRegistration({ login, email: e });
                if (existingUser.emailVerified) {
                    const finalized = await finalizeVerifiedAccount(existingUser, login);
                    if (!finalized.ok) return finalized;
                    return { ok: true, email: e, completed: true, login: finalized.login };
                }

                const resent = await sendVerificationWithCooldown(existingUser);
                clearSession();
                return resent.ok
                    ? { ok: true, email: e, recovered: true }
                    : { ok: false, email: e, needVerify: true, error: resent.error };
            } catch (recoveryError) {
                const recoveryCode = recoveryError?.code || "";
                if (["auth/wrong-password", "auth/invalid-credential", "auth/invalid-login-credentials"].includes(recoveryCode)) {
                    return { ok: false, error: "Этот email уже занят. Войди или восстанови пароль" };
                }
                if (recoveryCode === "auth/too-many-requests") {
                    return { ok: false, error: "Слишком много попыток. Попробуй позже" };
                }
                return { ok: false, error: "Не удалось восстановить регистрацию. Попробуй войти" };
            } finally {
                registrationRecoveryInProgress = false;
            }
        }
        if (code === "auth/invalid-email") return { ok: false, error: "Некорректный email" };
        if (code === "auth/weak-password") return { ok: false, error: "Слабый пароль (минимум 6 символов)" };
        return { ok: false, error: "Ошибка регистрации: " + code };
    }

    const userAuth = cred.user;
    // Persist the intended login before sending the email. If delivery fails or
    // the page reloads, the already-created Auth account can still be completed.
    setPendingRegistration({ login, email: e });
    const sent = await sendVerificationWithCooldown(userAuth);
    if (!sent.ok) {
        clearSession();
        return { ok: false, email: e, needVerify: true, error: sent.error };
    }

    clearSession();
    return { ok: true, email: e };
}

async function register() {
    clearErrors();
    const login = document.getElementById("reg-user").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const pass = document.getElementById("reg-pass").value.trim();

    if (!isLoginValid(login)) return showError("reg-error", "Логин: 3-16 символов, латиница/цифры/_");
    if (!normalizeEmail(email)) return showError("reg-error", "Укажи email");
    if (pass.length < 6) return showError("reg-error", "Пароль минимум 6 символов");
    if (!window.__captchaReady || !captchaToken) {
        setRegisterButtonEnabled(false, "Сначала пройди капчу");
        return showError("reg-error", "Подтверди reCAPTCHA");
    }

    const captchaVerification = await verifyCaptchaToken(captchaToken);
    if (!captchaVerification.ok) {
        resetTurnstileWidget();
        return showError("reg-error", captchaVerification.error);
    }

    const result = await registerUser(login, email, pass);
    if (!result.ok) {
        resetTurnstileWidget();
        if (result.needVerify) {
            showVerifyScreen(result.email, result.error);
            return;
        }
        return showError("reg-error", result.error);
    }

    resetTurnstileWidget();
    if (result.completed) {
        const next = new URLSearchParams(window.location.search).get("next");
        window.location.href = safeNextTarget(next);
        return;
    }
    showVerifyScreen(result.email, "Письмо отправлено. Подтверди email и нажми «Я подтвердил, проверить».");
}

async function resendVerificationFromForm() {
    clearErrors();
    const auth = getAuth();
    if (!auth) return showError("verify-error", "Firebase Auth не инициализирован");

    const pending = getPendingRegistration();
    if (!pending) return showError("verify-error", "Нет активной регистрации для подтверждения");

    const userAuth = auth.currentUser;
    if (!userAuth) return showError("verify-error", "Открой письмо и перейди по ссылке, затем нажми проверку");

    await userAuth.reload();
    if (userAuth.emailVerified) {
        const finalized = await finalizeVerifiedAccount(userAuth, pending.login);
        if (!finalized.ok) return showError("verify-error", finalized.error);
        const next = new URLSearchParams(window.location.search).get("next");
        window.location.href = safeNextTarget(next);
        return;
    }

    const sent = await sendVerificationWithCooldown(userAuth);
    if (!sent.ok) return showError("verify-error", sent.error);
    showError("verify-error", "Ссылка подтверждения отправлена повторно");
}

async function finalizeVerifiedAccount(userAuth, fallbackLogin = null) {
    const pending = getPendingRegistration();
    const storedLogin = getUser();
    const storedUid = getUid();
    let loginFromMap = null;
    try {
        loginFromMap = await resolveLoginByUidOrEmail(userAuth.uid, userAuth.email);
    } catch (err) {
        // A temporary RTDB/network failure must not turn a still-valid Firebase
        // session into a guest session. The stored values are display hints only;
        // protected API calls continue to use the verified Firebase ID token.
        if (storedLogin && storedUid === userAuth.uid) {
            return { ok: true, login: storedLogin, cached: true };
        }
        throw err;
    }

    if (loginFromMap) {
        clearPendingRegistration();
        setUser(loginFromMap);
        setUid(userAuth.uid);
        return { ok: true, login: loginFromMap };
    }

    if (!fallbackLogin && !(pending && pending.login) && storedLogin && storedUid === userAuth.uid) {
        return { ok: true, login: storedLogin, cached: true };
    }

    const login = loginFromMap || fallbackLogin || (pending && pending.login) || null;
    if (!login || login.startsWith("pending_")) {
        return { ok: false, error: "Логин не найден. Начни регистрацию заново." };
    }

    let finalizedLogin;
    try {
        finalizedLogin = await ensureUserProfile(login, userAuth);
    } catch (err) {
        const code = String(err?.message || "");
        if (code === "LOGIN_TAKEN") {
            return { ok: false, error: "Этот логин уже занят. Начни регистрацию заново." };
        }
        if (code === "EMAIL_NOT_VERIFIED") {
            return { ok: false, error: "Email ещё не подтверждён. Открой ссылку из письма и попробуй снова." };
        }
        if (code === "EMAIL_TAKEN" || code === "IDENTITY_CONFLICT") {
            return { ok: false, error: "Этот аккаунт уже связан с другим логином. Войди через форму входа." };
        }
        if (code === "RATE_LIMIT_EXCEEDED") {
            return { ok: false, error: "Слишком много попыток. Подожди несколько минут." };
        }
        return { ok: false, error: "Не удалось синхронизировать профиль. Попробуй ещё раз." };
    }
    clearPendingRegistration();
    setUser(finalizedLogin);
    setUid(userAuth.uid);
    return { ok: true, login: finalizedLogin };
}

async function checkVerificationStatus() {
    clearErrors();
    const auth = getAuth();
    if (!auth) return showError("verify-error", "Firebase Auth не инициализирован");

    const pending = getPendingRegistration();
    if (!pending) return showError("verify-error", "Нет активной регистрации");

    const userAuth = auth.currentUser;
    if (!userAuth) {
        return showError("verify-error", "Сессия подтверждения потеряна. Войди по email и паролю.");
    }

    await userAuth.reload();
    if (!userAuth.emailVerified) {
        return showError("verify-error", "Email еще не подтвержден");
    }

    const finalized = await finalizeVerifiedAccount(userAuth, pending.login);
    if (!finalized.ok) return showError("verify-error", finalized.error);
    const next = new URLSearchParams(window.location.search).get("next");
    window.location.href = safeNextTarget(next);
}

async function cancelPendingRegistration() {
    clearErrors();
    const auth = getAuth();
    const pending = getPendingRegistration();
    try {
        if (auth?.currentUser && !auth.currentUser.emailVerified) {
            await auth.currentUser.delete();
        } else if (auth?.currentUser) {
            await auth.signOut();
        }
    } catch (err) {
        // Требует recent login, но мы все равно чистим локальный pending.
        console.warn("cancelPendingRegistration", err);
    }
    clearPendingRegistration();
    clearSession();
    showError("verify-error", "Регистрация отменена");
    if (pending?.email) {
        showVerifyScreen(pending.email, "Регистрация отменена. Можно начать заново.");
    }
    const loginScreen = document.getElementById("screen-login");
    const regScreen = document.getElementById("screen-register");
    const verifyScreen = document.getElementById("screen-verify");
    if (loginScreen) loginScreen.style.display = "none";
    if (verifyScreen) verifyScreen.style.display = "none";
    if (regScreen) regScreen.style.display = "block";
}


/* ============================
   IMAGE URL UPLOAD
============================ */
async function prepareImageUpload(file, type) {
    if (!file.type.startsWith("image/")) throw new Error("Выбери изображение");
    if (file.size > 20 * 1024 * 1024) throw new Error("Изображение слишком большое (максимум 20 МБ)");
    if (file.type === "image/gif" || file.type === "image/svg+xml" || typeof createImageBitmap !== "function") return file;
    let bitmap;
    try {
        bitmap = await createImageBitmap(file);
        const limit = type === "avatar" ? 768 : type === "competitionLogo" ? 512 : 1600;
        const scale = Math.min(1, limit / Math.max(bitmap.width, bitmap.height));
        if (scale === 1 && file.size < 200000) return file;
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(bitmap.width * scale));
        canvas.height = Math.max(1, Math.round(bitmap.height * scale));
        canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/webp", .86));
        if (!blob || blob.size >= file.size) return file;
        return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".webp", { type: "image/webp" });
    } catch (_) { return file; }
    finally { bitmap?.close(); }
}

async function uploadImage(file, type) {
    const allowedTypes = ["avatar", "cover", "competitionLogo"];
    if (!file) throw new Error("Файл не выбран");
    if (!allowedTypes.includes(type)) throw new Error("Неверный тип изображения");

    const config = window.CODEBUG_CLOUDINARY || window.CODEBUG_PUBLIC_CONFIG?.cloudinary || {
        cloudName: "dez5af9sr",
        uploadPreset: "codebug_uploads"
    };
    if (!config.cloudName || !config.uploadPreset) {
        throw new Error("Загрузка изображений не настроена");
    }

    const formData = new FormData();
    formData.append("file", await prepareImageUpload(file, type));
    formData.append("upload_preset", config.uploadPreset);
    formData.append("folder", "codebug/" + type);

    const response = await fetch("https://api.cloudinary.com/v1_1/" + config.cloudName + "/image/upload", {
        method: "POST",
        body: formData
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.secure_url) {
        throw new Error(data.error?.message || "Ошибка загрузки изображения");
    }
    return data.secure_url;
}

function getOptimizedCloudinaryUrl(url, transformation) {
    const raw = String(url || "").trim();
    if (!raw || !transformation) return raw;

    let parsed;
    try {
        parsed = new URL(raw, window.location.origin);
    } catch (_) {
        return raw;
    }

    if (!/res\.cloudinary\.com$/i.test(parsed.hostname)) return raw;
    const marker = "/image/upload/";
    const markerIndex = parsed.pathname.indexOf(marker);
    if (markerIndex < 0) return raw;

    const before = parsed.pathname.slice(0, markerIndex + marker.length);
    let after = parsed.pathname.slice(markerIndex + marker.length);
    if (/^f_auto,q_auto,[^/]+\//.test(after)) after = after.slice(after.indexOf("/") + 1);
    if (!after || after.startsWith(transformation + "/")) return raw;

    parsed.pathname = before + transformation + "/" + after;
    return parsed.toString();
}

function getOptimizedAvatarUrl(url, size = 96) {
    size = Math.max(48, Math.min(512, Math.round(Number(size) || 96)));
    return getOptimizedCloudinaryUrl(url, `f_auto,q_auto,c_fill,w_${size},h_${size}`);
}

function getOptimizedCoverUrl(url, width = 480, height = 0) {
    width = Math.max(240, Math.min(1600, Math.round(Number(width) || 480)));
    return getOptimizedCloudinaryUrl(url, height ? `f_auto,q_auto,c_fill,w_${width},h_${Math.round(height)}` : `f_auto,q_auto,c_limit,w_${width}`);
}

async function saveAvatarUrl(login, avatarUrl) {
    const updatedAt = Date.now();
    await db.ref().update({
        ["users/" + login + "/avatarUrl"]: avatarUrl,
        ["users/" + login + "/updatedAt"]: updatedAt,
        ["publicProfiles/" + login + "/avatarUrl"]: avatarUrl,
        ["publicProfiles/" + login + "/updatedAt"]: updatedAt,
        ["ratingLeaderboard/" + login + "/avatarUrl"]: avatarUrl,
        ["ratingLeaderboard/" + login + "/updatedAt"]: updatedAt
    });
    const previous = CodeBugData.read("profile:" + login);
    if (previous) CodeBugData.write("profile:" + login, { ...previous, avatarUrl });
    else CodeBugData.invalidate("profile:" + login);
    clearNavbarIdentityCache(login);
}

async function saveCoverUrl(login, coverUrl) {
    const updatedAt = Date.now();
    await db.ref().update({
        ["users/" + login + "/coverUrl"]: coverUrl,
        ["users/" + login + "/updatedAt"]: updatedAt,
        ["publicProfiles/" + login + "/coverUrl"]: coverUrl,
        ["publicProfiles/" + login + "/updatedAt"]: updatedAt
    });
    const previous = CodeBugData.read("profile:" + login);
    if (previous) CodeBugData.write("profile:" + login, { ...previous, coverUrl });
    else CodeBugData.invalidate("profile:" + login);
}

async function saveCompetitionLogoUrl(competitionId, logoUrl) {
    return db.ref("competitions/" + competitionId).update({
        logoUrl,
        updatedAt: Date.now()
    });
}


/* ============================
   AUTH SESSION SYNC
============================ */
function isAuthPage() {
    return window.location.pathname.endsWith("/auth.html") || window.location.pathname.endsWith("auth.html");
}

function enforcePendingVerificationGuard() {
    const pending = getPendingRegistration();
    if (!pending) return;
    if (isAuthPage()) {
        showVerifyScreen(pending.email, "Подтверди email, чтобы завершить регистрацию.");
        return;
    }
    redirectToAuthForVerification();
}

async function syncSessionFromAuth() {
    if (registrationRecoveryInProgress) return;
    const auth = getAuth();
    if (!auth) return;
    const previousLogin = getUser();
    const userAuth = auth.currentUser;
    if (!userAuth) {
        clearSession();
        enforcePendingVerificationGuard();
        return;
    }
    await userAuth.reload();
    if (!userAuth.emailVerified) {
        clearSession();
        const currentPending = getPendingRegistration();
        const mappedLogin = await resolveLoginByUidOrEmail(userAuth.uid, userAuth.email);
        const loginForPending = (currentPending && currentPending.login) || mappedLogin || ("pending_" + userAuth.uid);
        setPendingRegistration({ login: loginForPending, email: normalizeEmail(userAuth.email) });
        enforcePendingVerificationGuard();
        return;
    }
    const finalized = await finalizeVerifiedAccount(userAuth, null);
    if (!finalized.ok) {
        // Firebase still considers this user authenticated. Keep the existing
        // local display session and retry naturally on the next page/load.
        return;
    }
    try {
        const token = await userAuth.getIdToken();
        if (token) localStorage.setItem("idToken", token);
    } catch (e) {
        console.warn("syncSessionFromAuth token fetch failed", e);
    }

    const nav = document.getElementById("nav-links");
    if (nav && (previousLogin !== finalized.login || nav.querySelector(".nav-auth-link"))) {
        updateNavbar();
    }

    if (isAuthPage()) {
        const next = new URLSearchParams(window.location.search).get("next");
        window.location.href = safeNextTarget(next);
    }
}

(() => {
    const auth = getAuth();
    if (!auth) {
        if (window.__firebaseConfigError) {
            showError("login-error", "Firebase не настроен на сервере");
            showError("reg-error", "Firebase не настроен на сервере");
        }
        return;
    }
    enforcePendingVerificationGuard();
    resumeGoogleRedirect();
    auth.onAuthStateChanged(async () => {
        try {
            if (localStorage.getItem("forceSignout") === "1") {
                localStorage.removeItem("forceSignout");
                if (auth.currentUser) await auth.signOut();
                clearSession();
                return;
            }
            await syncSessionFromAuth();
        } catch (err) {
            console.warn("auth sync failed", err);
        }
    });
})();

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", ensureGlobalFooter, { once: true });
    } else {
        ensureGlobalFooter();
    }
}



/* ============================
   ICONS
   One duotone set for the whole site: a soft fill inside the closed shape
   plus a 1.6 stroke. Every icon is drawn on a 24 grid and takes its colour
   from the element, so a row can stay green or amber without extra files.
============================ */
const CODEBUG_ICONS = {
    rank: '<path d="M7 4h10v4.5a5 5 0 0 1-10 0V4Z" fill="currentColor" fill-opacity=".18"/><path d="M7 5.6H4.6v1A4.4 4.4 0 0 0 8 10.9"/><path d="M17 5.6h2.4v1A4.4 4.4 0 0 1 16 10.9"/><path d="M12 13.5V17"/><path d="M8.5 20h7"/>',
    check: '<path d="M4.8 12.6 9.6 17.4 19.2 6.8"/>',
    target: '<circle cx="12" cy="12" r="8.4" fill="currentColor" fill-opacity=".18"/><circle cx="12" cy="12" r="4.6"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
    xp: '<path d="M12 3.3 20 7.65v8.7L12 20.7 4 16.35v-8.7Z" fill="currentColor" fill-opacity=".18"/><path d="M9.3 13.3 12 9.6l2.7 3.7"/>',
    retry: '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20.3 4.1v4.7h-4.7"/>',
    pulse: '<path d="M3 12.6h3.6L9.3 6l3.4 12 2.5-5.4H21"/>',
    edit: '<path d="M4 20.2h4.2L18.6 9.8a2.95 2.95 0 0 0-4.2-4.2L4 16v4.2Z" fill="currentColor" fill-opacity=".18"/><path d="m13.6 6.4 4.2 4.2"/>',
    crown: '<path d="M4 8.2 7.6 12 12 5.4 16.4 12 20 8.2 18.4 17.6H5.6L4 8.2Z" fill="currentColor" fill-opacity=".18"/><path d="M5.8 20.2h12.4"/>',
    clock: '<circle cx="12" cy="12" r="8.4" fill="currentColor" fill-opacity=".18"/><path d="M12 6.9v5.4l3.4 2"/>',
    bell: '<path d="M15 17H9m10-2.5c-.9-1-1.5-1.8-1.5-5A5.5 5.5 0 0 0 12 4a5.5 5.5 0 0 0-5.5 5.5c0 3.2-.6 4-1.5 5-.4.4-.1 1.1.5 1.1h13c.6 0 .9-.7.5-1.1Z" fill="currentColor" fill-opacity=".18"/><path d="M10 19a2 2 0 0 0 4 0"/>',
    menu: '<path d="M4 7h16"/><path d="M4 12h16"/><path d="M4 17h16"/>',
    arrow: '<path d="M5 12h13"/><path d="m12.6 6.6 5.4 5.4-5.4 5.4"/>',
    chevron: '<path d="m8 10.3 4 4 4-4"/>',
    flame: '<path d="M12 3.5c3.4 3 5 5.6 5 8.3a5 5 0 0 1-10 0c0-1.2.4-2.3 1.2-3.4.5 1 1.2 1.6 2 1.8-.4-2.6.2-4.8 1.8-6.7Z" fill="currentColor" fill-opacity=".18"/>'
};

function codebugIcon(name, options) {
    const inner = CODEBUG_ICONS[name];
    if (!inner) return "";
    const opts = options || {};
    const size = Number(opts.size) || 20;
    const cls = opts.className ? ` class="${opts.className}"` : "";
    return `<svg${cls} viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor"` +
        ` stroke-width="${opts.stroke || 1.6}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${inner}</svg>`;
}

/* Fills every <element data-icon="name"> on the page. Pages that build markup
   later call window.codebugFillIcons(root) on the part they just inserted. */
function codebugFillIcons(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("[data-icon]").forEach((el) => {
        const name = el.getAttribute("data-icon");
        if (!name || el.firstElementChild) return;
        el.innerHTML = codebugIcon(name, { size: Number(el.getAttribute("data-icon-size")) || 20 });
    });
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => codebugFillIcons(), { once: true });
    } else {
        codebugFillIcons();
    }
}

/* ============================
   EXPORT GLOBAL (for HTML)
============================ */
window.updateNavbar = updateNavbar;
window.codebugTagRu = codebugTagRu;
window.codebugIcon = codebugIcon;
window.codebugFillIcons = codebugFillIcons;
window.codebugPlural = codebugPlural;
window.login = login;
window.register = register;
window.loginWithGoogle = loginWithGoogle;
window.completeGoogleLogin = completeGoogleLogin;
window.cancelGoogleLogin = cancelGoogleLogin;
window.forgotPassword = forgotPassword;
window.resendVerificationFromForm = resendVerificationFromForm;
window.checkVerificationStatus = checkVerificationStatus;
window.cancelPendingRegistration = cancelPendingRegistration;
window.showVerifyScreen = showVerifyScreen;
window.isRegistrationLocked = isRegistrationLocked;
window.getPendingRegistrationSafe = getPendingRegistration;
window.renderCaptchaWidget = renderCaptchaWidget;
window.renderTurnstileWidget = renderCaptchaWidget;
window.updateAvatar = function() {};
window.logout = logout;
window.waitForAuthUser = waitForAuthUser;
window.getFreshAuthToken = getFreshAuthToken;
window.getUserSubscription = getUserSubscription;
window.isProSubscription = isProSubscription;
window.getSubscriptionLevel = getSubscriptionLevel;
window.hasSubscriptionAtLeast = hasSubscriptionAtLeast;
window.getSubscriptionNickTheme = getSubscriptionNickTheme;
window.getSubscriptionNickColor = getSubscriptionNickColor;

window.getUser = getUser;
window.getUid = getUid;
if (!window.db && db) window.db = db;
window.uploadImage = uploadImage;
window.getOptimizedAvatarUrl = getOptimizedAvatarUrl;
window.getOptimizedCoverUrl = getOptimizedCoverUrl;
window.saveAvatarUrl = saveAvatarUrl;
window.saveCoverUrl = saveCoverUrl;
window.saveCompetitionLogoUrl = saveCompetitionLogoUrl;
window.startPresence = startPresence;
