// === Firebase INIT (v8) via runtime public config === //

(function bootstrapCodeBugConfig() {
    const defaultApiBase = (location.hostname === "localhost")
        ? "http://localhost:7777"
        : "https://codebug.onrender.com";

    window.TASKS_API_BASE = (window.TASKS_API_BASE || window.CODEBUG_API_BASE || defaultApiBase).replace(/\/$/, "");
    window.getTasksApiBase = function getTasksApiBase() {
        return (window.TASKS_API_BASE || window.CODEBUG_API_BASE || defaultApiBase).replace(/\/$/, "");
    };

    function loadPublicConfigSync() {
        if (window.CODEBUG_PUBLIC_CONFIG && typeof window.CODEBUG_PUBLIC_CONFIG === "object") {
            return window.CODEBUG_PUBLIC_CONFIG;
        }

        try {
            const xhr = new XMLHttpRequest();
            xhr.open("GET", window.TASKS_API_BASE + "/public-config", false);
            xhr.send(null);
            if (xhr.status >= 200 && xhr.status < 300) {
                return JSON.parse(xhr.responseText || "{}");
            }
            console.error("public-config status:", xhr.status, xhr.responseText);
        } catch (err) {
            console.error("public-config request failed:", err);
        }
        return {};
    }

    const runtimeConfig = loadPublicConfigSync();
    window.CODEBUG_PUBLIC_CONFIG = runtimeConfig;
    window.RECAPTCHA_SITE_KEY = runtimeConfig.recaptchaSiteKey || "";

    const firebaseConfig = runtimeConfig.firebase || {};
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
