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
   NAVIGATION BAR
============================ */
function updateNavbar() {
    const nav = document.getElementById("nav-links");
    if (!nav) return;

    const user = getUser();

    if (user) {
        nav.innerHTML = `
            <a href="index.html">Главная</a>
            <a href="archive.html">Архив</a>
            <a href="train.html">Тренировка</a>
            <a href="rating.html">Рейтинг</a>
            <a href="submissions.html">Посылки</a>
            <a href="donate.html">Донат</a>
            <a href="faq.html">FAQ</a>
            <a href="profile.html">${user}</a>
            <a onclick="logout()" style="cursor:pointer;color:#ffd451;">Выйти</a>
        `;
    } else {
        nav.innerHTML = `
            <a href="index.html">Главная</a>
            <a href="archive.html">Архив</a>
            <a href="train.html">Тренировка</a>
            <a href="rating.html">Рейтинг</a>
            <a href="donate.html">Донат</a>
            <a href="faq.html">FAQ</a>
            <a href="auth.html">Войти / Регистрация</a>
        `;
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

    if (data.password !== pass) {
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

    // внутренний UID
    const userId = "uid_" + Math.random().toString(36).substring(2, 10);



    const userObj = {
        login: login,
        id: userId,
        pass: pass, // В будущем лучше заменить на hash
        created: Date.now(),

        stats: {
            exp: 0,
            cnt: 0,
            solved: {}
        },

        avatar: "", // base64
        about: "" // BIO
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
    document.getElementById("captchaText").innerText = `${a} + ${b} = ?`;
    window.correctCaptcha = a + b;
}
generateCaptcha();


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