const { expect } = require("@playwright/test");

const NOW = Date.now();
const TEST_USER = {
  uid: "e2e-user-uid",
  login: "e2e_user",
  email: "e2e_user@codebug.test",
  password: "Testpass1",
  token: "e2e-id-token"
};

function firebaseMockScript({ authenticated = false, plan = "free" } = {}) {
  return ({ authenticated: initialAuthenticated, plan: initialPlan }) => {
    const safeClone = (value) => JSON.parse(JSON.stringify(value));
    const getAt = (root, path) => String(path || "").split("/").filter(Boolean)
      .reduce((value, part) => (value && typeof value === "object" ? value[part] : undefined), root);
    const setAt = (root, path, value) => {
      const parts = String(path || "").split("/").filter(Boolean);
      if (!parts.length) {
        Object.keys(root).forEach((key) => delete root[key]);
        Object.assign(root, safeClone(value));
        return;
      }
      let target = root;
      parts.slice(0, -1).forEach((part) => {
        if (!target[part] || typeof target[part] !== "object") target[part] = {};
        target = target[part];
      });
      target[parts.at(-1)] = safeClone(value);
    };
    const testUser = {
      uid: "e2e-user-uid",
      login: "e2e_user",
      email: "e2e_user@codebug.test",
      password: "Testpass1",
      token: "e2e-id-token"
    };
    const subscription = initialPlan === "pro_plus"
      ? { tier: "pro_plus", status: "active", expiresAt: Date.now() + 86_400_000 }
      : null;
    const store = {
      users: {
        [testUser.login]: {
          id: testUser.uid,
          email: testUser.email,
          subscription,
          stats: { exp: 42, cnt: 3, rating: 17, solved: { "101": true } },
          presence: { online: true, lastSeen: Date.now() }
        }
      },
      publicProfiles: {
        [testUser.login]: {
          login: testUser.login,
          subscription,
          stats: { exp: 42, cnt: 3, rating: 17 },
          profileStyle: { coverId: "cover_1" }
        }
      },
      ratingLeaderboard: {
        [testUser.login]: { login: testUser.login, exp: 42, cnt: 3, rating: 17 }
      },
      userAuthMap: { [testUser.uid]: testUser.login },
      emailToLogin: { "e2e_user%40codebug.test": testUser.login },
      contests: {
        "e2e-contest": {
          title: "E2E Контест",
          description: "Проверка пользовательского пути",
          visibility: "public",
          ownerLogin: "organizer",
          authors: ["organizer"],
          tasks: [101],
          start: Date.now() - 3_600_000,
          end: Date.now() + 3_600_000
        }
      },
      contest_regs: { "e2e-contest": {} },
      submissions: {
        global: {
          "e2e-submission": { login: testUser.login, task: 101, verdict: "OK", date: Date.now() - 1_000 }
        }
      },
      admins: {}
    };
    let authUser = null;
    let listeners = [];
    const notify = () => listeners.forEach((listener) => Promise.resolve().then(() => listener(authUser)));
    const makeUser = (email = testUser.email, verified = true) => ({
      uid: testUser.uid,
      email,
      emailVerified: verified,
      async reload() { return this; },
      async getIdToken() { return testUser.token; },
      async sendEmailVerification() { return undefined; },
      async delete() { authUser = null; localStorage.removeItem("e2e-authenticated"); notify(); }
    });
    if (initialAuthenticated || localStorage.getItem("e2e-authenticated") === "1") {
      authUser = makeUser();
      localStorage.setItem("e2e-authenticated", "1");
      localStorage.setItem("user", testUser.login);
      localStorage.setItem("uid", testUser.uid);
      localStorage.setItem("idToken", testUser.token);
    }

    const makeSnapshot = (value) => ({
      exists: () => value !== undefined && value !== null,
      val: () => safeClone(value),
      forEach: (callback) => {
        if (!value || typeof value !== "object") return false;
        return Object.entries(value).some(([key, child]) => callback({ key, val: () => safeClone(child), exists: () => child != null }));
      }
    });
    let pushId = 0;
    const ref = (path = "") => ({
      async get() { return makeSnapshot(getAt(store, path)); },
      async once() { return makeSnapshot(getAt(store, path)); },
      async set(value) { setAt(store, path, value); },
      async update(value) {
        Object.entries(value || {}).forEach(([key, item]) => setAt(store, [path, key].filter(Boolean).join("/"), item));
      },
      async remove() { setAt(store, path, null); },
      push() { const key = `e2e-${++pushId}`; return { key, set: async (value) => setAt(store, [path, key].filter(Boolean).join("/"), value) }; },
      orderByChild() { return this; },
      equalTo() { return this; },
      limitToLast() { return this; },
      on() { return () => {}; },
      off() {},
      onDisconnect() { return { set: async () => undefined }; }
    });
    const database = () => ({ ref, goOffline() {}, goOnline() {} });
    database.INTERNAL = { forceLongPolling() {}, forceWebSockets() {} };
    database.ServerValue = { TIMESTAMP: Date.now() };
    const auth = () => ({
      get currentUser() { return authUser; },
      onAuthStateChanged(callback) { listeners.push(callback); Promise.resolve().then(() => callback(authUser)); return () => { listeners = listeners.filter((item) => item !== callback); }; },
      async signInWithEmailAndPassword(email, password) {
        if (String(email).toLowerCase() !== testUser.email || password !== testUser.password) {
          const error = new Error("invalid credentials"); error.code = "auth/invalid-credential"; throw error;
        }
        authUser = makeUser(); localStorage.setItem("e2e-authenticated", "1"); notify(); return { user: authUser };
      },
      async signInWithCustomToken(token) {
        if (token !== "e2e-custom-token") {
          const error = new Error("invalid custom token"); error.code = "auth/invalid-custom-token"; throw error;
        }
        authUser = makeUser(); localStorage.setItem("e2e-authenticated", "1"); notify(); return { user: authUser };
      },
      async createUserWithEmailAndPassword(email) {
        authUser = makeUser(email, false); notify(); return { user: authUser };
      },
      async sendPasswordResetEmail(email) {
        if (!email) { const error = new Error("invalid email"); error.code = "auth/invalid-email"; throw error; }
      },
      async signOut() { authUser = null; localStorage.removeItem("e2e-authenticated"); notify(); }
    });
    window.CODEBUG_PUBLIC_CONFIG = {
      recaptchaSiteKey: "e2e-captcha-key",
      firebase: { apiKey: "e2e", authDomain: "e2e.test", databaseURL: "https://e2e-db.test", projectId: "e2e", storageBucket: "e2e", messagingSenderId: "e2e", appId: "e2e" }
    };
    const completeCaptcha = () => Promise.resolve().then(() => window.__e2eCaptchaOptions?.callback("e2e-captcha-token"));
    window.grecaptcha = {
      render(_host, options) { window.__e2eCaptchaOptions = options; completeCaptcha(); return 1; },
      reset() { completeCaptcha(); }
    };
    window.firebase = {
      apps: [],
      initializeApp(config) { this.apps = [{ options: config }]; return this.apps[0]; },
      database,
      auth
    };
    window.__e2eStore = store;
  };
}

async function mockExternalServices(page) {
  await page.route(/https:\/\/(www\.gstatic\.com\/firebasejs|www\.google\.com\/recaptcha|cdnjs\.cloudflare\.com\/ajax\/libs\/monaco-editor)\/.*/, (route) => route.fulfill({ status: 200, contentType: "application/javascript", body: "" }));
  await page.route("**/auth/verify-captcha", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true }) }));
  await page.route("**/auth/login", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, customToken: "e2e-custom-token", login: TEST_USER.login }) }));
  await page.route("**/auth/password-reset", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true }) }));
  await page.route("**/auth/finalize-profile", async (route) => {
    const body = route.request().postDataJSON?.() || {};
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, login: body.login || TEST_USER.login }) });
  });
  await page.route("**/submit", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "OK", statusLabel: "OK", score: 100, timeMs: 12, memoryMb: 3.5, passedGroups: [1], firebaseSaved: true }) }));
  await page.route("**/contest/register", async (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true }) }));
  await page.route("**/contests/create", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, contestId: "created-e2e" }) }));
  await page.route("**/tasks/101/problem.json", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ title: "Сумма двух чисел", language: "cpp", difficulty: "easy", tags: ["math"], statement: { markdown: "statement.md" }, files: { code: "code.cpp" }, openTests: [{ name: "1", input: "tests/1.in", answer: "tests/1.out" }] }) }));
  await page.route("**/tasks/101/meta.json", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ title: "Сумма двух чисел", language: "cpp", difficulty: "easy" }) }));
  await page.route("**/tasks/101/statement.md", (route) => route.fulfill({ contentType: "text/plain", body: "# Сумма\nДаны два числа." }));
  await page.route("**/tasks/101/code.cpp", (route) => route.fulfill({ contentType: "text/plain", body: "#include <iostream>\nint main() {}" }));
  await page.route("**/tasks/101/tests/1.in", (route) => route.fulfill({ contentType: "text/plain", body: "1 2\n" }));
  await page.route("**/tasks/101/tests/1.out", (route) => route.fulfill({ contentType: "text/plain", body: "3\n" }));
  await page.route("**/tasks/list", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify([{ id: 101, title: "Сумма двух чисел", difficulty: "easy", tags: ["math"] }]) }));
  const profile = { login: TEST_USER.login, stats: { exp: 42, cnt: 1, rating: 17 }, profileStyle: { coverId: "cover_1" } };
  const submissions = {
    "e2e-submission": { login: TEST_USER.login, task: 101, verdict: "OK", date: Date.now() - 1_000 }
  };
  await page.route("**/users/e2e_user/profile-lite", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(profile) }));
  await page.route("https://e2e-db.test/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = path.includes("publicProfiles/e2e_user")
      ? profile
      : path.includes("submissions/global")
        ? submissions
        : {};
    return route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
}

async function preparePage(page, options = {}) {
  await page.addInitScript(firebaseMockScript(options), options);
  await mockExternalServices(page);
}

async function signInThroughUi(page) {
  await page.goto("/auth.html");
  await page.locator("#login-identity").fill(TEST_USER.login);
  await page.locator("#login-pass").fill(TEST_USER.password);
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page).toHaveURL(/index\.html$/);
}

module.exports = { TEST_USER, expect, preparePage, signInThroughUi };
