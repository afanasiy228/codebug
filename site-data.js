/* Small, versioned snapshots survive full-page navigation. The server remains
   authoritative for access, registration, subscriptions and judging. */
(() => {
    const PREFIX = "codebug:data:v1:";
    const memory = new Map();
    const pending = new Map();
    const unavailable = new Set();
    let generation = 0;
    const DAY = 86400000;
    const base = () => window.getTasksApiBase ? window.getTasksApiBase() : (window.TASKS_API_BASE || "https://codebug.onrender.com");
    const scoped = key => PREFIX + base() + ":" + key;
    function read(key, maxAge = DAY) {
        try {
            const id = scoped(key);
            const item = memory.get(id) || JSON.parse(localStorage.getItem(id) || "null");
            if (!item || item.version !== 1 || Date.now() - item.at > maxAge) return null;
            memory.set(id, item);
            return item.data;
        } catch (_) { return null; }
    }
    function fresh(key, ttl) {
        read(key);
        const item = memory.get(scoped(key));
        return !!item && Date.now() - item.at < ttl;
    }
    function write(key, data) {
        const item = { version: 1, at: Date.now(), data };
        const id = scoped(key);
        memory.set(id, item);
        try {
            const value = JSON.stringify(item);
            if (value.length > 1500000) return data;
            // Bound the snapshot store. A full/quota-disabled store is harmless.
            const keys = Object.keys(localStorage).filter(k => k.startsWith(PREFIX));
            if (keys.length >= 60) {
                keys.sort((a, b) => {
                    try { return JSON.parse(localStorage.getItem(a)).at - JSON.parse(localStorage.getItem(b)).at; }
                    catch (_) { return 0; }
                });
                keys.slice(0, 15).forEach(k => { localStorage.removeItem(k); memory.delete(k); });
            }
            localStorage.setItem(id, value);
        } catch (_) {}
        return data;
    }
    function invalidate(prefix = "") {
        generation++;
        for (const key of memory.keys()) if (key.startsWith(scoped(prefix))) memory.delete(key);
        // In-flight older responses must not repopulate a cleared session.
        for (const key of pending.keys()) if (key.startsWith(scoped(prefix))) pending.delete(key);
        try {
            Object.keys(localStorage).filter(key => key.startsWith(scoped(prefix))).forEach(key => localStorage.removeItem(key));
        } catch (_) {}
    }
    async function load(key, loader, { ttl = 30000, force = false } = {}) {
        if (!force && fresh(key, ttl)) return read(key);
        const id = scoped(key);
        if (!force && pending.has(id)) return pending.get(id);
        const epoch = generation;
        const promise = Promise.resolve().then(loader).then(data => {
            if (epoch === generation && pending.get(id) === promise) write(key, data);
            return data;
        }).finally(() => { if (pending.get(id) === promise) pending.delete(id); });
        pending.set(id, promise);
        return promise;
    }
    function swr(key, loader, render, options = {}) {
        const cached = read(key, options.maxAge || DAY);
        if (cached !== null) render(cached, true);
        return load(key, loader, options).then(data => {
            if (data !== cached) render(data, false);
            return data;
        });
    }
    async function json(path, options = {}) {
        const { timeout = 6000, ...init } = options;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeout);
        try {
            const response = await fetch(path.startsWith("http") ? path : base() + path, { ...init, signal: controller.signal });
            if (!response.ok) {
                const error = new Error("HTTP " + response.status);
                error.status = response.status;
                throw error;
            }
            return await response.json();
        } finally { clearTimeout(timer); }
    }
    async function optional(path, fallback, options) {
        if (!unavailable.has(path)) {
            try { return await json(path, options); }
            catch (error) {
                if (![404, 405, 501].includes(error.status)) throw error;
                unavailable.add(path);
            }
        }
        return fallback();
    }
    const privateKey = (login, resource) => "private:" + (window.getUid?.() || login) + ":" + resource;
    function deadline(promise, milliseconds = 2600) {
        let timer;
        return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("read_timeout")), milliseconds); })]).finally(() => clearTimeout(timer));
    }
    function profile(login, options = {}) {
        return load("profile:" + login, () => json("/users/" + encodeURIComponent(login) + "/profile-lite", options.force ? { cache: "reload" } : {}).catch(async error => {
            if (error.status === 404) { invalidate("profile:" + login); throw error; }
            const snap = await deadline(window.db.ref("publicProfiles/" + login).get());
            if (!snap.exists()) throw error;
            return { ...snap.val(), login };
        }), { ttl: 30000, ...options });
    }
    const catalog = options => load("catalog", () => optional("/tasks/catalog", async () => {
        const data = await json("/tasks/list");
        return data.filter(task => task.visibility !== "private" && task.verificationStatus !== "pending");
    }), { ttl: 60000, ...options });
    async function submissions({ login, contestId, force = false } = {}) {
        const currentLogin = window.getUser?.();
        const key = contestId ? (currentLogin ? privateKey(currentLogin, "contest-submissions:" + contestId) : "contest-submissions:" + contestId) : "submissions:" + login;
        const path = contestId ? "/contests/" + encodeURIComponent(contestId) + "/submissions" : "/users/" + encodeURIComponent(login) + "/submissions";
        return load(key, async () => {
            const token = contestId && currentLogin ? await window.getFreshAuthToken?.() : null;
            return optional(path, async () => {
            const field = contestId ? "contestId" : "login";
            const value = contestId || login;
            let ref = window.db.ref("submissions/global");
            if (ref.orderByChild) ref = ref.orderByChild(field).equalTo(value);
            const snap = await deadline(ref.get());
            return Object.entries(snap.val() || {}).map(([id, item]) => ({ ...item, _id: id })).filter(item => item[field] === value);
            }, { ...(force ? { cache: "reload" } : {}), ...(token ? { headers: { Authorization: `Bearer ${token}` } } : {}) });
        }, { ttl: 15000, force });
    }
    function changed(login) {
        invalidate("submissions:" + login);
        invalidate("private:");
        invalidate("profile:" + login);
        invalidate("contest-submissions:");
        invalidate("leaderboard");
        window.dispatchEvent(new CustomEvent("codebug:data-changed", { detail: { login } }));
    }
    function mark(name) { try { performance.mark("codebug:" + name); } catch (_) {} }
    function deferVisible(element, callback) {
        if (!element || !("IntersectionObserver" in window)) { callback(); return; }
        const observer = new IntersectionObserver(entries => {
            if (entries.some(entry => entry.isIntersecting)) { observer.disconnect(); callback(); }
        }, { rootMargin: "240px" });
        observer.observe(element);
    }
    window.CodeBugData = { read, write, fresh, load, swr, invalidate, json, optional, profile, catalog, submissions, privateKey, changed, mark, deferVisible, deadline };
})();
