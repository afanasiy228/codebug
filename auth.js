/* ============================
   FIREBASE INIT
============================ */
if (!firebase.apps.length) {
    firebase.initializeApp({
        apiKey: "AIzaSyDkQTqt1Hcg7H-a4rVl88dCbdJkDEiPDEg",
        authDomain: "codebug-47347.firebaseapp.com",
        databaseURL: "https://codebug-47347-default-rtdb.europe-west1.firebasedatabase.app",
        projectId: "codebug-47347",
        storageBucket: "codebug-47347.appspot.com", // ← исправлено !!!
        messagingSenderId: "1000157426060",
        appId: "1:1000157426060:web:4350f2d9f3db75e407e6a9"
    });
}
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
    const user = getUser();

    if (!nav) return;

    if (user) {
        nav.innerHTML = `
            <a href="index.html">Главная</a>
            <a href="archive.html">Архив</a>
            <a href="train.html">Тренировка</a>
            <a href="rating.html">Рейтинг</a>
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
            <a href="rating.html">Рейтинг</а>
            <a href="donate.html">Донат</a>
            <a href="faq.html">FAQ</a>
            <a href="auth.html">Войти / Зарегистрироваться</a>
        `;
    }
}


/* ============================
   ERROR DISPLAY HELPERS
============================ */
function showError(id, text) {
    const elem = document.getElementById(id);
    if (elem) elem.innerText = text;
}

function clearErrors() {
    showError("login-error", "");
    showError("reg-error", "");
    document.querySelectorAll("input").forEach(i => i.classList.remove("input-error"));
}


/* ============================
   SIMPLE ID GENERATOR
============================ */
function generateId() {
    // Простой псевдо-UUID, для системы хватит
    return "xxxxxx-xxxxxx-xxxxxx".replace(/x/g, () =>
        (Math.random() * 16 | 0).toString(16)
    );
}


/* ============================
   LOGIN FUNCTIONS
============================ */
async function loginUser(login, pass) {
    const snapshot = await db.ref("users/" + login).get();

    if (!snapshot.exists()) {
        return { ok: false, error: "Пользователь не найден" };
    }

    const userData = snapshot.val();

    if (userData.password !== pass) {
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
   REGISTER FUNCTIONS
============================ */
async function registerUser(login, pass) {
    const ref = db.ref("users/" + login);
    const snapshot = await ref.get();

    if (snapshot.exists()) {
        return { ok: false, error: "Логин уже занят" };
    }

    // генерируем внутренний ID
    const userId = "uid_" + Math.random().toString(36).substring(2, 10);

    // минимум статистики, как ты просил
    const stats = {
        solved: 69,
        exp: 1789,
        lastSolved: [8, 8, 4, 1]
    };

    await ref.set({
        id: userId,
        login: login,
        password: pass,
        avatarUrl: null,
        created: Date.now(),
        stats: stats
    });

    return { ok: true };
}

async function register() {
    clearErrors();

    const login = document.getElementById("reg-user").value.trim();
    const pass = document.getElementById("reg-pass").value.trim();
    const captcha = document.getElementById("captchaAnswer").value.trim();

    if (login.length < 3) {
        showError("reg-error", "Логин слишком короткий");
        return;
    }

    if (login.length > 16) {
        showError("reg-error", "Максимум 16 символов");
        return;
    }

    if (pass.length < 3) {
        showError("reg-error", "Пароль слишком короткий");
        return;
    }

    if (parseInt(captcha) !== window.correctCaptcha) {
        showError("reg-error", "Капча неверная");
        return;
    }

    const result = await registerUser(login, pass);

    if (!result.ok) {
        showError("reg-error", result.error);
        return;
    }

    setUser(login);
    window.location.href = "profile.html";
}

/* ============================
   UI HELPERS
============================ */
function updateAvatar() {
    let login = document.getElementById("reg-user").value;
    let box = document.getElementById("avatarPreview");
    if (!box) return;

    if (login.length === 0) {
        box.textContent = "A";
        box.style.background = "#333";
        return;
    }
    box.textContent = login[0].toUpperCase();
    box.style.background = "#" + Math.floor(Math.random() * 16777215).toString(16);
}
/* ============================
   UPLOAD AVATAR
============================ */
/* ============================
   AVATAR UPLOAD (BASE64)
============================ */
async function uploadAvatarBase64(login, file) {
    return new Promise((resolve, reject) => {
        if (!file) {
            resolve(null);
            return;
        }

        const reader = new FileReader();

        reader.onload = function(e) {
            resolve(e.target.result); // base64 string
        };

        reader.onerror = function() {
            reject("Ошибка чтения файла");
        };

        reader.readAsDataURL(file); // convert to base64
    });
}

/* save avatar */
async function saveAvatar(login, base64) {
    await db.ref("users/" + login + "/avatar").set(base64);
}

function generateCaptcha() {
    const a = Math.floor(Math.random() * 5 + 1);
    const b = Math.floor(Math.random() * 5 + 1);
    document.getElementById("captchaText").innerText = `${a} + ${b} = ?`;
    window.correctCaptcha = a + b;
}
generateCaptcha();


/* ============================
   MAKE GLOBAL
============================ */
window.updateNavbar = updateNavbar;
window.login = login;
window.register = register;
window.updateAvatar = updateAvatar;
window.generateCaptcha = generateCaptcha;
window.logout = logout;

// нужно для profile.html, rating.html и других страниц
window.getUser = getUser;
window.db = db; // чтобы можно было использовать db в других 
window.uploadAvatarBase64 = uploadAvatarBase64;
window.saveAvatar = saveAvatar;