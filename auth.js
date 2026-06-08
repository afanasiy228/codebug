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
    if (document.getElementById("mobile-nav-style")) return;
    const style = document.createElement("style");
    style.id = "mobile-nav-style";
    style.textContent = `
header, .top-nav {
    background: rgba(5, 5, 5, 0.88) !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35) !important;
    backdrop-filter: blur(10px) !important;
}
header .logo, .top-nav .logo {
    color: #FFFFFF !important;
}
header .brand-code, .top-nav .brand-code {
    color: #ffffff !important;
}
header .brand-bug, .top-nav .brand-bug {
    color: #ffffff !important;
}
header .brand-suffix, .top-nav .brand-suffix {
    color: #ffffff !important;
}
header nav a, .top-nav nav a {
    color: #b0b0b0 !important;
}
header nav a:hover, .top-nav nav a:hover {
    color: #FBBF24 !important;
}
#nav-links {
    display: flex;
    align-items: center;
    margin-left: auto;
    gap: 16px;
}
#nav-links .nav-shell {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 24px;
    width: 100%;
    position: relative;
    z-index: 2002;
}
#nav-links .nav-links {
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
}
#nav-links .nav-primary {
    justify-content: flex-end;
}
#nav-links .nav-account {
    gap: 12px;
}
#nav-links .nav-account .nav-profile {
    padding: 6px 12px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: #121212;
    color: #FFFFFF !important;
    font-weight: 700;
}
#nav-links .nav-account .nav-profile:hover {
    color: #ffffff !important;
    border-color: rgba(245, 158, 11, 0.55);
    background: rgba(245, 158, 11, 0.15);
}
#nav-links .nav-burger {
    display: none;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: #121212;
    color: #FFFFFF;
    font-size: 20px;
    cursor: pointer;
    position: relative;
    z-index: 2003;
}
#nav-links .nav-drawer {
    display: none;
    position: fixed;
    top: 0;
    right: -320px;
    width: 280px;
    height: 100%;
    background: #0B0B0B;
    padding: 80px 20px 24px;
    box-shadow: -20px 0 40px rgba(0, 0, 0, 0.45);
    z-index: 2002;
    gap: 12px;
    flex-direction: column;
    transition: right 0.25s ease;
    pointer-events: none;
}
#nav-links .nav-drawer a {
    margin: 0;
    display: block;
    padding: 10px 0;
    color: #FFFFFF !important;
    text-decoration: none;
}
#nav-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
    z-index: 2001;
}
body.nav-open #nav-overlay {
    opacity: 1;
    pointer-events: auto;
}
body.nav-open #nav-links .nav-drawer {
    right: 0;
    pointer-events: auto;
}
@media (max-width: 900px) {
    #nav-links .nav-links {
        display: none;
    }
    #nav-links .nav-burger {
        display: inline-flex;
    }
    #nav-links .nav-drawer {
        display: flex;
    }
}
`;
    document.head.appendChild(style);
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
        if (window.innerWidth > 900) closeMenu();
    });
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

function updateNavbar() {
    const nav = document.getElementById("nav-links");
    if (!nav) return;

    const logos = document.querySelectorAll(".logo");
    logos.forEach((logo) => {
        if (logo.querySelector("a")) return;
        const text = (logo.textContent || "CodeBug").trim() || "CodeBug";
        logo.innerHTML = `<a href="index.html" style="color:inherit;text-decoration:none;">${buildCodeBugBrandHtml(text)}</a>`;
    });

    const user = getUser();
    ensureMobileNavStyles();

    const commonLinks = `
        <a href="train.html">Тренировка</a>
        <a href="contests.html">Соревнования</a>
        <a href="rating.html">Рейтинг</a>
        <a href="donate.html">Донат</a>
        <a href="faq.html">Помощь</a>
    `;

    const accountLinks = user
        ? `
           <a href="submissions.html">Посылки</a>
           <a href="profile.html" class="nav-profile">${user}</a>`
        : `<a href="auth.html">Войти / Регистрация</a>`;

    const drawerLinks = `${commonLinks}${accountLinks}`;

    nav.innerHTML = `
        <div class="nav-shell">
            <div class="nav-links nav-primary">${commonLinks}</div>
            <div class="nav-links nav-account">${accountLinks}</div>
            <button class="nav-burger" type="button" aria-label="Меню" aria-expanded="false">☰</button>
        </div>
        <div class="nav-drawer" aria-hidden="true">${drawerLinks}</div>
    `;

    bindMobileNav(nav);
    startKeepAlive();
    applyProBrandingToNavbar(user).catch(() => {});
}

async function getUserSubscription(login) {
    if (!login || !window.firebase) return null;
    try {
        const snap = await firebase.database().ref("users/" + login + "/subscription").get();
        if (!snap.exists()) return null;
        const val = snap.val() || {};
        return {
            tier: String(val.tier || "").toLowerCase(),
            status: String(val.status || "").toLowerCase(),
            expiresAt: val.expiresAt || null,
            graceUntil: val.graceUntil || val.paymentGraceUntil || null,
            daysLeft: val.daysLeft ?? null,
            graceDaysLeft: val.graceDaysLeft ?? null,
            paymentWarning: val.paymentWarning || null,
            features: (val.features && typeof val.features === "object") ? val.features : {},
            visuals: (val.visuals && typeof val.visuals === "object") ? val.visuals : {}
        };
    } catch (_) {
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
    return "#FFFFFF";
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
    const sub = await getUserSubscription(login);
    let exp = 0;
    try {
        const userSnap = await firebase.database().ref("users/" + login + "/stats/exp").get();
        if (userSnap.exists()) exp = Number(userSnap.val() || 0);
    } catch (_) {}
    const level = getSubscriptionLevel(sub);
    const isPro = level !== "free";
    const nickColor = isPro ? getSubscriptionNickColor(sub) : getRankNickColorByExp(exp);
    const navProfile = document.querySelector("#nav-links .nav-profile");
    if (navProfile) {
        navProfile.style.setProperty("color", isPro ? "#FBBF24" : "#FFFFFF", "important");
        navProfile.style.fontWeight = "700";
        if (isPro) {
            const badge = level === "pro_plus" ? "PRO+" : "PRO";
            if (!navProfile.textContent.includes("PRO")) {
                navProfile.textContent = `${login} · ${badge}`;
            }
        } else {
            navProfile.textContent = login;
        }
    }
    if (!isPro) return;
    const logos = document.querySelectorAll(".logo a");
    logos.forEach((logo) => {
        logo.innerHTML = buildCodeBugBrandHtml("CodeBug PRO");
    });
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
            <a class="cb-legal-btn" href="https://telegra.ph/Politika-konfidencialnosti-04-01-26" target="_blank" rel="noopener">Политика конфиденциальности</a>
            <a class="cb-legal-btn" href="https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19" target="_blank" rel="noopener">Пользовательское соглашение</a>
            <a class="cb-legal-btn" href="https://t.me/afony_l" target="_blank" rel="noopener">Поддержка: @afony_l</a>
            <a class="cb-legal-btn" href="mailto:support@codebug.online">support@codebug.online</a>
        </div>
    `;

    const style = document.createElement("style");
    style.textContent = `
        #global-legal-footer {
            margin-top: 28px;
            padding: 12px 10px 18px;
            border-top: 1px solid rgba(148, 163, 184, 0.22);
            background: rgba(2, 6, 23, 0.18);
        }
        .cb-legal-footer-inner {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
            justify-content: center;
            text-align: center;
        }
        #global-legal-footer .cb-legal-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 30px;
            padding: 0 10px;
            border: 1px solid rgba(148, 163, 184, 0.35);
            border-radius: 8px;
            color: #B0B0B0;
            font-size: 12px;
            line-height: 1;
            text-decoration: none;
            white-space: nowrap;
        }
        #global-legal-footer .cb-legal-btn:hover {
            border-color: rgba(125, 211, 252, 0.75);
            color: #FFFFFF;
            background: rgba(18, 18, 18, 0.9);
        }
        @media (max-width: 700px) {
            .cb-legal-footer-inner {
                justify-content: center;
            }
        }
    `;

    document.head.appendChild(style);
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
}


/* ============================
   FIREBASE AUTH HELPERS
============================ */
var EMAIL_RETRY_COOLDOWN_MS = 60 * 1000;
var lastVerificationSentAt = 0;
var PENDING_REG_KEY = "pendingRegistration";
var RECAPTCHA_PLACEHOLDER_KEY = "PASTE_RECAPTCHA_SITE_KEY_HERE";
var captchaWidgetId = null;
var captchaToken = "";
window.__captchaReady = !!window.__captchaReady;

function getAuth() {
    if (!window.firebase || typeof firebase.auth !== "function") return null;
    return firebase.auth();
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
    const e = normalizeEmail(email);
    if (e) {
        const emailSnap = await db.ref("emailToLogin/" + emailKey(e)).get();
        if (emailSnap.exists()) return emailSnap.val();
    }
    return null;
}

async function resolveEmailByIdentity(identity) {
    const raw = String(identity || "").trim();
    if (!raw) return null;
    if (raw.includes("@")) return normalizeEmail(raw);
    const snap = await db.ref("users/" + raw + "/email").get();
    if (!snap.exists()) return null;
    return normalizeEmail(snap.val());
}

async function ensureUserProfile(login, userAuth) {
    const now = Date.now();
    const baseStats = {
        exp: 0,
        cnt: 0,
        rating: 0,
        solved: {}
    };
    const lightStats = {
        exp: 0,
        cnt: 0,
        rating: 0
    };
    const idSnap = await db.ref("users/" + login + "/id").get();
    if (!idSnap.exists()) {
        await db.ref().update({
            ["users/" + login]: {
                login,
                id: userAuth.uid,
                email: normalizeEmail(userAuth.email),
                emailVerified: !!userAuth.emailVerified,
                created: now,
                stats: baseStats,
                avatarUrl: "",
                coverUrl: "",
                updatedAt: now
            },
            ["publicProfiles/" + login]: {
                login,
                avatarUrl: "",
                coverUrl: "",
                stats: lightStats,
                profileStyle: { coverId: null },
                subscription: null,
                updatedAt: now
            },
            ["ratingLeaderboard/" + login]: {
                login,
                exp: 0,
                cnt: 0,
                rating: 0,
                avatarUrl: "",
                profileStyle: { coverId: null },
                subscription: null,
                updatedAt: now
            }
        });
    } else {
        await db.ref().update({
            ["users/" + login + "/id"]: userAuth.uid,
            ["users/" + login + "/email"]: normalizeEmail(userAuth.email),
            ["users/" + login + "/emailVerified"]: !!userAuth.emailVerified,
            ["users/" + login + "/updatedAt"]: now,
            ["publicProfiles/" + login + "/login"]: login,
            ["publicProfiles/" + login + "/updatedAt"]: now,
            ["ratingLeaderboard/" + login + "/login"]: login,
            ["ratingLeaderboard/" + login + "/updatedAt"]: now
        });
    }

    await db.ref("userAuthMap/" + userAuth.uid).set(login);
    if (userAuth.email) {
        await db.ref("emailToLogin/" + emailKey(userAuth.email)).set(login);
    }
}

async function loginUser(email, pass) {
    const auth = getAuth();
    if (!auth) return { ok: false, error: "Firebase Auth не инициализирован" };

    let cred;
    try {
        cred = await auth.signInWithEmailAndPassword(normalizeEmail(email), pass);
    } catch (err) {
        const code = err?.code || "";
        if (code === "auth/user-not-found") return { ok: false, error: "Пользователь не найден" };
        if (code === "auth/wrong-password") return { ok: false, error: "Неверный пароль" };
        if (code === "auth/invalid-email") return { ok: false, error: "Некорректный email" };
        return { ok: false, error: "Ошибка входа: " + code };
    }

    await cred.user.reload();
    const userAuth = auth.currentUser || cred.user;
    if (!userAuth.emailVerified) {
        return { ok: false, needVerify: true, userAuth, error: "Подтверди email перед входом" };
    }

    return { ok: true, userAuth };
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
    if (pass.length < 6) return showError("login-error", "Пароль слишком короткий");

    const email = await resolveEmailByIdentity(identity);
    if (!email) return showError("login-error", "Пользователь не найден");

    const result = await loginUser(email, pass);
    if (!result.ok) {
        if (result.needVerify && result.userAuth) {
            const pendingLogin = await resolveLoginByUidOrEmail(result.userAuth.uid, result.userAuth.email) || String(identity);
            setPendingRegistration({ login: pendingLogin, email });
            const sent = await sendVerificationWithCooldown(result.userAuth);
            if (!sent.ok) {
                showVerifyScreen(email, `${result.error}. ${sent.error}`);
                return;
            }
            showVerifyScreen(email, "Email не подтвержден. Отправили новую ссылку.");
            return;
        }
        return showError("login-error", result.error);
    }

    const finalized = await finalizeVerifiedAccount(result.userAuth, null);
    if (!finalized.ok) return showError("login-error", finalized.error);

    const next = new URLSearchParams(window.location.search).get("next");
    window.location.href = next || "index.html";
}

async function forgotPassword() {
    clearErrors();
    const auth = getAuth();
    if (!auth) return showError("login-error", "Firebase Auth не инициализирован");

    const identity = document.getElementById("login-identity").value.trim();
    if (!identity) return showError("login-error", "Укажи логин или email для восстановления");

    const email = await resolveEmailByIdentity(identity);
    if (!email) return showError("login-error", "Пользователь не найден");

    try {
        await auth.sendPasswordResetEmail(normalizeEmail(email));
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

    const snap = await db.ref("users/" + login + "/id").get();
    if (snap.exists()) return { ok: false, error: "Логин уже занят" };

    const e = normalizeEmail(email);
    const mailMapSnap = await db.ref("emailToLogin/" + emailKey(e)).get();
    if (mailMapSnap.exists()) return { ok: false, error: "Этот email уже используется" };

    let cred;
    try {
        cred = await auth.createUserWithEmailAndPassword(e, pass);
    } catch (err) {
        const code = err?.code || "";
        if (code === "auth/email-already-in-use") return { ok: false, error: "Этот email уже занят" };
        if (code === "auth/invalid-email") return { ok: false, error: "Некорректный email" };
        if (code === "auth/weak-password") return { ok: false, error: "Слабый пароль (минимум 6 символов)" };
        return { ok: false, error: "Ошибка регистрации: " + code };
    }

    const userAuth = cred.user;
    const sent = await sendVerificationWithCooldown(userAuth);
    if (!sent.ok) return { ok: false, error: sent.error };

    setPendingRegistration({ login, email: e });
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
        return showError("reg-error", result.error);
    }

    resetTurnstileWidget();
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
        window.location.href = next || "index.html";
        return;
    }

    const sent = await sendVerificationWithCooldown(userAuth);
    if (!sent.ok) return showError("verify-error", sent.error);
    showError("verify-error", "Ссылка подтверждения отправлена повторно");
}

async function finalizeVerifiedAccount(userAuth, fallbackLogin = null) {
    const pending = getPendingRegistration();
    const loginFromMap = await resolveLoginByUidOrEmail(userAuth.uid, userAuth.email);
    const login = loginFromMap || fallbackLogin || (pending && pending.login) || null;
    if (!login || login.startsWith("pending_")) {
        return { ok: false, error: "Логин не найден. Начни регистрацию заново." };
    }

    const existingRef = db.ref("users/" + login + "/id");
    const existingSnap = await existingRef.get();
    if (existingSnap.exists() && existingSnap.val() !== userAuth.uid) {
        return { ok: false, error: "Этот логин уже занят. Начни регистрацию заново." };
    }

    await ensureUserProfile(login, userAuth);
    clearPendingRegistration();
    setUser(login);
    setUid(userAuth.uid);
    return { ok: true, login };
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
    window.location.href = next || "index.html";
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
    formData.append("file", file);
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
    const after = parsed.pathname.slice(markerIndex + marker.length);
    if (!after || after.startsWith(transformation + "/")) return raw;

    parsed.pathname = before + transformation + "/" + after;
    return parsed.toString();
}

function getOptimizedAvatarUrl(url) {
    return getOptimizedCloudinaryUrl(url, "f_auto,q_auto,c_fill,w_256,h_256");
}

function getOptimizedCoverUrl(url) {
    return getOptimizedCloudinaryUrl(url, "f_auto,q_auto,c_limit,w_1600");
}

async function saveAvatarUrl(login, avatarUrl) {
    const updatedAt = Date.now();
    return db.ref().update({
        ["users/" + login + "/avatarUrl"]: avatarUrl,
        ["users/" + login + "/updatedAt"]: updatedAt,
        ["publicProfiles/" + login + "/avatarUrl"]: avatarUrl,
        ["publicProfiles/" + login + "/updatedAt"]: updatedAt,
        ["ratingLeaderboard/" + login + "/avatarUrl"]: avatarUrl,
        ["ratingLeaderboard/" + login + "/updatedAt"]: updatedAt
    });
}

async function saveCoverUrl(login, coverUrl) {
    const updatedAt = Date.now();
    return db.ref().update({
        ["users/" + login + "/coverUrl"]: coverUrl,
        ["users/" + login + "/updatedAt"]: updatedAt,
        ["publicProfiles/" + login + "/coverUrl"]: coverUrl,
        ["publicProfiles/" + login + "/updatedAt"]: updatedAt
    });
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
    const auth = getAuth();
    if (!auth) return;
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
        clearSession();
        return;
    }
    try {
        const token = await userAuth.getIdToken();
        if (token) localStorage.setItem("idToken", token);
    } catch (e) {
        console.warn("syncSessionFromAuth token fetch failed", e);
    }

    if (isAuthPage()) {
        const next = new URLSearchParams(window.location.search).get("next");
        window.location.href = next || "index.html";
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
   EXPORT GLOBAL (for HTML)
============================ */
window.updateNavbar = updateNavbar;
window.login = login;
window.register = register;
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
