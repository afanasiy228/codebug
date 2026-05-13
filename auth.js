/* ============================
   FIREBASE INIT
============================ */
const db = firebase.database();


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

/* ============================
   MOBILE NAV (BURGER)
============================ */
function ensureMobileNavStyles() {
    if (document.getElementById("mobile-nav-style")) return;
    const style = document.createElement("style");
    style.id = "mobile-nav-style";
    style.textContent = `
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
    border-radius: 999px;
    border: 1px solid rgba(0, 0, 0, 0.15);
    background: rgba(255, 255, 255, 0.65);
    color: var(--ink) !important;
    font-weight: 700;
}
#nav-links .nav-account .nav-profile:hover {
    color: var(--accent) !important;
}
#nav-links .nav-burger {
    display: none;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    border: 1px solid rgba(0, 0, 0, 0.15);
    background: rgba(255, 255, 255, 0.8);
    font-size: 20px;
    cursor: pointer;
}
#nav-links .nav-drawer {
    display: none;
    position: fixed;
    top: 0;
    right: -320px;
    width: 280px;
    height: 100%;
    background: #fffaf2;
    padding: 80px 20px 24px;
    box-shadow: -20px 0 40px rgba(0, 0, 0, 0.12);
    z-index: 1001;
    gap: 12px;
    flex-direction: column;
    transition: right 0.25s ease;
}
#nav-links .nav-drawer a {
    margin: 0;
}
#nav-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
    z-index: 1000;
}
body.nav-open #nav-overlay {
    opacity: 1;
    pointer-events: auto;
}
body.nav-open #nav-links .nav-drawer {
    right: 0;
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
    try {
        const snap = await db.ref("admins/" + user).get();
        return snap.exists();
    } catch (err) {
        console.warn("Admin check failed", err);
        return false;
    }
}


/* ============================
   NAVIGATION BAR
============================ */
function updateNavbar() {
    const nav = document.getElementById("nav-links");
    if (!nav) return;

    const user = getUser();
    ensureMobileNavStyles();

    const commonLinks = `
        <a href="index.html">Главная</a>
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
        lastSeen: Date.now()
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
}


/* ============================
   FIREBASE AUTH HELPERS
============================ */
const EMAIL_RETRY_COOLDOWN_MS = 60 * 1000;
let lastVerificationSentAt = 0;

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
    const profileRef = db.ref("users/" + login);
    const snap = await profileRef.get();
    if (!snap.exists()) {
        await profileRef.set({
            login,
            id: userAuth.uid,
            email: normalizeEmail(userAuth.email),
            emailVerified: !!userAuth.emailVerified,
            created: Date.now(),
            stats: {
                exp: 0,
                cnt: 0,
                solved: {}
            },
            avatar: ""
        });
    } else {
        await profileRef.update({
            id: userAuth.uid,
            email: normalizeEmail(userAuth.email),
            emailVerified: !!userAuth.emailVerified,
            updatedAt: Date.now()
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

    const login = await resolveLoginByUidOrEmail(userAuth.uid, userAuth.email);
    if (!login) {
        return { ok: false, error: "Профиль не найден. Обратись к админу." };
    }

    await ensureUserProfile(login, userAuth);
    return { ok: true, login, uid: userAuth.uid };
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
            const sent = await sendVerificationWithCooldown(result.userAuth);
            if (!sent.ok) return showError("login-error", `${result.error}. ${sent.error}`);
            return showError("login-error", "Email не подтвержден. Отправили новое письмо.");
        }
        return showError("login-error", result.error);
    }

    setUser(result.login);
    setUid(result.uid);
    window.location.href = "index.html";
}

async function registerUser(login, email, pass) {
    const auth = getAuth();
    if (!auth) return { ok: false, error: "Firebase Auth не инициализирован" };

    const profileRef = db.ref("users/" + login);
    const snap = await profileRef.get();
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
    await ensureUserProfile(login, userAuth);
    const sent = await sendVerificationWithCooldown(userAuth);
    await auth.signOut();
    setUid(null);
    return sent.ok
        ? { ok: true }
        : { ok: false, error: sent.error };
}

async function register() {
    clearErrors();
    const login = document.getElementById("reg-user").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const pass = document.getElementById("reg-pass").value.trim();
    const captcha = document.getElementById("captchaAnswer").value.trim();

    if (!isLoginValid(login)) return showError("reg-error", "Логин: 3-16 символов, латиница/цифры/_");
    if (!normalizeEmail(email)) return showError("reg-error", "Укажи email");
    if (pass.length < 6) return showError("reg-error", "Пароль минимум 6 символов");
    if (parseInt(captcha) !== window.correctCaptcha) return showError("reg-error", "Капча неверная");

    const result = await registerUser(login, email, pass);
    if (!result.ok) return showError("reg-error", result.error);

    showError("reg-error", "Письмо подтверждения отправлено. Подтверди email и войди.");
    goLogin();
}

async function resendVerificationFromForm() {
    clearErrors();
    const auth = getAuth();
    if (!auth) return showError("reg-error", "Firebase Auth не инициализирован");

    const email = document.getElementById("reg-email").value.trim();
    const pass = document.getElementById("reg-pass").value.trim();
    if (!normalizeEmail(email) || !pass) {
        return showError("reg-error", "Введи email и пароль для повторной отправки");
    }

    try {
        const cred = await auth.signInWithEmailAndPassword(normalizeEmail(email), pass);
        await cred.user.reload();
        if (cred.user.emailVerified) {
            await auth.signOut();
            return showError("reg-error", "Email уже подтвержден");
        }
        const sent = await sendVerificationWithCooldown(cred.user);
        await auth.signOut();
        if (!sent.ok) return showError("reg-error", sent.error);
        showError("reg-error", "Письмо подтверждения отправлено повторно");
    } catch (err) {
        showError("reg-error", "Не удалось отправить письмо: " + (err?.code || "unknown"));
    }
}


/* ============================
   AVATAR BASE64
============================ */
async function uploadAvatarBase64(login, file) {
    return new Promise((resolve, reject) => {
        if (!file) return resolve(null);

        const reader = new FileReader();

        reader.onload = e => resolve(e.target.result);
        reader.onerror = () => reject("Ошибка чтения файла");

        reader.readAsDataURL(file);
    });
}

async function saveAvatar(login, base64) {
    return db.ref("users/" + login + "/avatar").set(base64);
}


/* ============================
   CAPTCHA
============================ */
function generateCaptcha() {
    const a = Math.floor(Math.random() * 5 + 1);
    const b = Math.floor(Math.random() * 5 + 1);
    const el = document.getElementById("captchaText");
    if (!el) return;
    el.innerText = `${a} + ${b} = ?`;
    window.correctCaptcha = a + b;
}
if (document.getElementById("captchaText")) {
    generateCaptcha();
}

/* ============================
   AUTH SESSION SYNC
============================ */
async function syncSessionFromAuth() {
    const auth = getAuth();
    if (!auth) return;
    const userAuth = auth.currentUser;
    if (!userAuth) {
        clearSession();
        return;
    }
    await userAuth.reload();
    if (!userAuth.emailVerified) {
        clearSession();
        return;
    }
    const login = await resolveLoginByUidOrEmail(userAuth.uid, userAuth.email);
    if (!login) {
        clearSession();
        return;
    }
    setUser(login);
    setUid(userAuth.uid);
}

(() => {
    const auth = getAuth();
    if (!auth) return;
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


/* ============================
   EXPORT GLOBAL (for HTML)
============================ */
window.updateNavbar = updateNavbar;
window.login = login;
window.register = register;
window.resendVerificationFromForm = resendVerificationFromForm;
window.updateAvatar = function() {};
window.generateCaptcha = generateCaptcha;
window.logout = logout;

window.getUser = getUser;
window.getUid = getUid;
window.db = db;
window.uploadAvatarBase64 = uploadAvatarBase64;
window.saveAvatar = saveAvatar;
window.startPresence = startPresence;
