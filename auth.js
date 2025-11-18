/* ===========================
      AUTH STORAGE
=========================== */

function getUser() {
    return localStorage.getItem("codebug_user");
}

function setUser(username) {
    // Защита от undefined
    if (!username || username === "undefined") return;

    localStorage.setItem("codebug_user", username);
}

function logout() {
    localStorage.removeItem("codebug_user");
    window.location.href = "index.html";
}


/* ===========================
      HEADER RENDER
=========================== */

function renderHeader() {
    const nav = document.getElementById("nav-links");
    if (!nav) return;

    let user = getUser();

    // защита от мусорных значений
    if (!user || user === "undefined" || user === "null" || user.trim() === "") {
        user = null;
    }

    if (user) {
        // ВОШЕДШИЙ ПОЛЬЗОВАТЕЛЬ
        nav.innerHTML = `
            <a href="index.html">Главная</a>
            <a href="archive.html">Архив</a>
            <a href="train.html">Тренировка</a>
            <a href="rating.html">Рейтинг</a>
            <a href="donate.html">Донат</a>
            <a href="faq.html">FAQ</a>
            <a href="profile.html">Профиль</a>
            <a href="#" onclick="logout()">Выйти</a>
        `;
    } else {
        // ГОСТЬ
        nav.innerHTML = `
            <a href="index.html">Главная</a>
            <a href="archive.html">Архив</a>
            <a href="train.html">Тренировка</a>
            <a href="rating.html">Рейтинг</a>
            <a href="donate.html">Донат</a>
            <a href="faq.html">FAQ</a>
            <a href="auth.html">Войти</a>
        `;
    }
}

renderHeader();


/* ===========================
      LOGIN
=========================== */

function login() {
    const user = document.getElementById("login-user").value.trim();
    const pass = document.getElementById("login-pass").value.trim();

    if (user.length === 0) {
        alert("Введите логин.");
        return;
    }
    if (pass.length === 0) {
        alert("Введите пароль.");
        return;
    }

    // Пароль не проверяем (фронтенд-версия)
    setUser(user);

    window.location.href = "index.html";
}


/* ===========================
      REGISTER
=========================== */

function register() {
    const u = document.getElementById("reg-user").value.trim();
    const p = document.getElementById("reg-pass").value.trim();
    const c = document.getElementById("captchaAnswer").value.trim();

    // Проверка капчи
    if (typeof correctCaptcha !== "undefined") {
        if (parseInt(c) !== correctCaptcha) {
            alert("Капча неверная!");
            correctCaptcha = generateCaptcha();
            return;
        }
    }

    if (u.length < 3) {
        alert("Логин должен содержать минимум 3 символа.");
        return;
    }

    if (p.length < 3) {
        alert("Пароль должен содержать минимум 3 символа.");
        return;
    }

    if (u.length > 30 || p.length > 30) {
        alert("Фока ты тупой?");
        return;
    }

    // Создаём "аккаунт"
    setUser(u);

    alert("Регистрация успешна!");
    window.location.href = "index.html";
}


/* ===========================
      CAPTCHA
=========================== */

function generateCaptcha() {
    let a = Math.floor(Math.random() * 5 + 1);
    let b = Math.floor(Math.random() * 5 + 1);
    let text = `${a} + ${b} = ?`;

    const place = document.getElementById("captchaText");
    if (place) {
        place.innerText = text;
    }

    return a + b;
}

if (document.getElementById("captchaText")) {
    window.correctCaptcha = generateCaptcha();
}