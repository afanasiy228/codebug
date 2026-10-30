// === Firebase INIT (v8) via runtime public config === //

(function bootstrapCodeBugConfig() {
    const defaultApiBase = (location.hostname === "localhost")
        ? "http://localhost:7777"
        : "https://codebug.onrender.com";

    window.TASKS_API_BASE = (window.TASKS_API_BASE || window.CODEBUG_API_BASE || defaultApiBase).replace(/\/$/, "");
    window.getTasksApiBase = function getTasksApiBase() {
        return (window.TASKS_API_BASE || window.CODEBUG_API_BASE || defaultApiBase).replace(/\/$/, "");
    };

    // Public configuration ships with the page; Render is never a startup dependency.
    let runtimeConfig = window.CODEBUG_PUBLIC_CONFIG || {};
    const configKey = "codebug:public-config:" + window.TASKS_API_BASE;
    if (window.CODEBUG_STATIC_CONFIG) {
        try {
            const saved = JSON.parse(localStorage.getItem(configKey) || "null");
            if (saved && Date.now() - saved.at < 86400000 && saved.data?.firebase?.projectId === runtimeConfig.firebase?.projectId) runtimeConfig = saved.data;
        } catch (_) {}
        // Prices and other public settings can refresh independently of Firebase initialization.
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        fetch(window.TASKS_API_BASE + "/public-config", { signal: controller.signal })
            .then(response => { if (!response.ok) throw new Error("public-config"); return response.json(); })
            .then(config => {
                if (config.firebase?.projectId !== runtimeConfig.firebase?.projectId) return;
                try { localStorage.setItem(configKey, JSON.stringify({ at: Date.now(), data: config })); } catch (_) {}
                window.CODEBUG_PUBLIC_CONFIG = config;
                window.RECAPTCHA_SITE_KEY = config.recaptchaSiteKey || "";
                window.dispatchEvent(new Event("codebug:config-updated"));
            }).catch(() => {}).finally(() => clearTimeout(timeout));
    }

    window.CODEBUG_PUBLIC_CONFIG = runtimeConfig;
    window.RECAPTCHA_SITE_KEY = runtimeConfig.recaptchaSiteKey || "";

    const firebaseConfig = runtimeConfig.firebase || {};
    // The Google sign-in helper is self-hosted at /__/auth/, so the Google window
    // shows codebug.online instead of the Firebase project domain.
    if (location.hostname === "codebug.online" || location.hostname === "www.codebug.online") {
        firebaseConfig.authDomain = location.hostname;
    }
    const requiredFirebaseKeys = [
        "apiKey",
        "authDomain",
        "databaseURL",
        "projectId",
        "storageBucket",
        "messagingSenderId",
        "appId"
    ];

    const missingFirebaseKeys = requiredFirebaseKeys.filter((key) => !firebaseConfig[key]);
    if (missingFirebaseKeys.length) {
        console.error("Firebase config missing keys:", missingFirebaseKeys.join(", "));
        window.__firebaseConfigError = "missing: " + missingFirebaseKeys.join(", ");
        return;
    }

    if (!window.firebase || typeof window.firebase.initializeApp !== "function") {
        window.__firebaseConfigError = "firebase_sdk_not_loaded";
        return;
    }

    // В некоторых сетях websocket до RTDB нестабилен/блокируется (частая причина "Client is offline").
    // По умолчанию используем long-polling, чтобы профиль и сабмиты не зависали.
    try {
        const internal = window.firebase.database?.INTERNAL;
        const mode = String(runtimeConfig.firebaseTransport || "").trim().toLowerCase();
        if (internal?.forceWebSockets && mode === "websocket") {
            internal.forceWebSockets();
            console.log("Firebase transport: websocket");
        } else if (internal?.forceLongPolling) {
            internal.forceLongPolling();
            console.log("Firebase transport: long-polling");
        }
    } catch (err) {
        console.warn("firebase transport setup failed:", err);
    }

    if (!firebase.apps || !firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
    }

    window.db = firebase.database();
    window.firebase = firebase;
    window.__firebaseConfigError = "";

    console.log("Firebase INIT OK, db =", window.db);
})();
