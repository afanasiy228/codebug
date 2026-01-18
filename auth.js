/* ============================
   FIREBASE INIT
============================ */
const db = firebase.database();


/* ============================
   USER SESSION
============================ */
function setUser(login) {
    localStorage.setItem("user", login);
}

function getUser() {
    return localStorage.getItem("user");
}

function logout() {
    localStorage.removeItem("user");
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
    gap: 16px;
}
#nav-links .nav-shell {
    display: flex;
    align-items: center;
    gap: 16px;
    width: 100%;
}
#nav-links .nav-links {
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
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
        <a href="news.html">Новости</a>
        <a href="faq.html">Помощь</a>
    `;

    const userLinks = user
        ? `${commonLinks}
           <a href="submissions.html">Посылки</a>
           <a href="profile.html">${user}</a>
           <a data-action="logout" style="cursor:pointer;color:#ffd451;">Выйти</a>`
        : `${commonLinks}
           <a href="auth.html">Войти / Регистрация</a>`;

    nav.innerHTML = `
        <div class="nav-shell">
            <div class="nav-links">${userLinks}</div>
            <button class="nav-burger" type="button" aria-label="Меню" aria-expanded="false">☰</button>
        </div>
        <div class="nav-drawer" aria-hidden="true">${userLinks}</div>
    `;

    nav.querySelectorAll("[data-action='logout']").forEach(link => {
        link.addEventListener("click", logout);
    });
    bindMobileNav(nav);
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
   GENERATE USER ID
============================ */
function generateId() {
    return "uid-" + Math.random().toString(36).substring(2, 10);
}


/* ============================
   LOGIN
============================ */
async function loginUser(login, pass) {
    const snapshot = await db.ref("users/" + login).get();

    if (!snapshot.exists()) {
        return { ok: false, error: "Пользователь не найден" };
    }

    const data = snapshot.val();

    if (data.pass !== pass) {
        return { ok: false, error: "Неверный пароль" };
    }

    return { ok: true };
}

async function login() {
    clearErrors();

    const login = document.getElementById("login-user").value.trim();
    const pass = document.getElementById("login-pass").value.trim();

    if (login.length < 3) {
        showError("login-error", "Логин слишком короткий");
        return;
    }
    if (pass.length < 3) {
        showError("login-error", "Пароль слишком короткий");
        return;
    }

    const result = await loginUser(login, pass);
    if (!result.ok) {
        showError("login-error", result.error);
        return;
    }

    setUser(login);
    window.location.href = "index.html";
}


/* ============================
   REGISTER
============================ */
async function registerUser(login, pass) {
    const ref = db.ref("users/" + login);
    const snap = await ref.get();

    if (snap.exists()) {
        return { ok: false, error: "Логин уже занят" };
    }

    const userId = "uid_" + Math.random().toString(36).substring(2, 10);

    const userObj = {
        login: login,
        id: userId,
        pass: pass,
        created: Date.now(),

        stats: {
            exp: 0,
            cnt: 0,
            solved: {}
        },

        avatar: "",
    };

    await ref.set(userObj);

    return { ok: true };
}

async function register() {
    clearErrors();

    const login = document.getElementById("reg-user").value.trim();
    const pass = document.getElementById("reg-pass").value.trim();
    const captcha = document.getElementById("captchaAnswer").value.trim();

    if (login.length < 3) return showError("reg-error", "Логин слишком короткий");
    if (login.length > 16) return showError("reg-error", "Максимум 16 символов");
    if (pass.length < 3) return showError("reg-error", "Пароль слишком короткий");
    if (parseInt(captcha) !== window.correctCaptcha) return showError("reg-error", "Капча неверная");

    const result = await registerUser(login, pass);

    if (!result.ok) {
        showError("reg-error", result.error);
        return;
    }

    setUser(login);
    window.location.href = "profile.html";
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
   EXPORT GLOBAL (for HTML)
============================ */
window.updateNavbar = updateNavbar;
window.login = login;
window.register = register;
window.updateAvatar = function() {};
window.generateCaptcha = generateCaptcha;
window.logout = logout;

window.getUser = getUser;
window.db = db;
window.uploadAvatarBase64 = uploadAvatarBase64;
window.saveAvatar = saveAvatar;
window.startPresence = startPresence;
