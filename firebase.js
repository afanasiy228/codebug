// === Firebase INIT (v8) via runtime public config === //

(function bootstrapCodeBugConfig() {
    const defaultApiBase = (location.hostname === "localhost")
        ? "http://localhost:7777"
        : "https://codebug.onrender.com";

    window.TASKS_API_BASE = (window.TASKS_API_BASE || window.CODEBUG_API_BASE || defaultApiBase).replace(/\/$/, "");

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
        throw new Error("Firebase config is not set. Configure /public-config on backend.");
    }

    if (!window.firebase || typeof window.firebase.initializeApp !== "function") {
        throw new Error("Firebase SDK is not loaded");
    }

    if (!firebase.apps || !firebase.apps.length) {
        firebase.initializeApp(firebaseConfig);
    }

    window.db = firebase.database();
    window.firebase = firebase;
    window.TURNSTILE_SITE_KEY = runtimeConfig.turnstileSiteKey || "";
    window.CODEBUG_PUBLIC_CONFIG = runtimeConfig;

    console.log("Firebase INIT OK, db =", window.db);
})();
