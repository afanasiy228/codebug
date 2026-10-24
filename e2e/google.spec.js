const { test } = require("@playwright/test");
const { TEST_USER, expect, preparePage } = require("./helpers/mock-codebug");

/**
 * Sign in with Google. The harness fakes Firebase without OAuth providers, so this
 * file adds GoogleAuthProvider and signInWithPopup on top of it. `mode` picks what
 * the fake Google popup returns.
 */
async function withGoogle(page, mode) {
  await preparePage(page);
  await page.addInitScript(({ mode, testUser }) => {
    const origAuth = window.firebase.auth;
    let googleUser = null;
    const makeGoogleUser = (uid, email) => ({
      uid,
      email,
      emailVerified: true,
      displayName: "Google User",
      async reload() {},
      async getIdToken() { return "e2e-google-token"; }
    });
    const auth = function () {
      const base = origAuth();
      const wrapped = Object.create(base);
      Object.defineProperty(wrapped, "currentUser", { get: () => googleUser || base.currentUser });
      wrapped.signInWithPopup = async () => {
        window.__googlePopupCalls = (window.__googlePopupCalls || 0) + 1;
        if (mode === "disabled") {
          const error = new Error("operation not allowed");
          error.code = "auth/operation-not-allowed";
          throw error;
        }
        googleUser = mode === "existing"
          ? makeGoogleUser(testUser.uid, testUser.email)
          : makeGoogleUser("google-new-uid", "new.coder@gmail.com");
        return { user: googleUser };
      };
      wrapped.signOut = async () => { googleUser = null; return base.signOut(); };
      return wrapped;
    };
    auth.GoogleAuthProvider = function GoogleAuthProvider() {
      this.setCustomParameters = () => {};
    };
    window.firebase.auth = auth;
  }, { mode, testUser: TEST_USER });
}

test.describe("Вход через Google", () => {
  test("новый пользователь выбирает логин и входит", async ({ page }) => {
    await withGoogle(page, "new");
    const finalize = [];
    page.on("request", (req) => {
      if (req.url().includes("/auth/finalize-profile")) finalize.push(req.postDataJSON());
    });

    await page.goto("/auth.html");
    await page.getByRole("button", { name: "Войти через Google" }).click();

    await expect(page.locator("#screen-google")).toBeVisible();
    await expect(page.locator("#google-email-label")).toHaveText("new.coder@gmail.com");
    await expect(page.locator("#google-login")).toHaveValue("new_coder");

    await page.locator("#google-login").fill("x");
    await page.getByRole("button", { name: "Готово" }).click();
    await expect(page.locator("#google-error")).toContainText("3-16 символов");

    await page.locator("#google-login").fill("new_coder");
    await page.getByRole("button", { name: "Готово" }).click();
    await expect(page).toHaveURL(/index\.html$/);
    expect(finalize.at(-1)).toEqual({ login: "new_coder" });
    expect(await page.evaluate(() => localStorage.getItem("user"))).toBe("new_coder");
  });

  test("привязанный аккаунт входит сразу", async ({ page }) => {
    await withGoogle(page, "existing");
    await page.goto("/auth.html?next=train.html");
    await page.getByRole("button", { name: "Войти через Google" }).click();
    await expect(page).toHaveURL(/train\.html$/);
    await expect(page.locator("#screen-google")).toHaveCount(0);
  });

  test("отмена выбора логина возвращает к форме входа", async ({ page }) => {
    await withGoogle(page, "new");
    await page.goto("/auth.html");
    await page.getByRole("button", { name: "Войти через Google" }).click();
    await expect(page.locator("#screen-google")).toBeVisible();
    await page.getByText("Отмена", { exact: true }).click();
    await expect(page.locator("#screen-login")).toBeVisible();
    await expect(page.locator("#screen-google")).toBeHidden();
  });

  test("если Google не включён, показывает понятную ошибку", async ({ page }) => {
    await withGoogle(page, "disabled");
    await page.goto("/auth.html");
    await page.getByRole("button", { name: "Войти через Google" }).click();
    await expect(page.locator("#login-error")).toContainText("Вход через Google пока не включён");
    await expect(page.locator("#screen-login")).toBeVisible();
  });

  test("кнопка есть и на экране регистрации", async ({ page }) => {
    await withGoogle(page, "new");
    await page.goto("/auth.html");
    await page.getByText("Нет аккаунта? Регистрация").click();
    await page.getByRole("button", { name: "Продолжить с Google" }).click();
    await expect(page.locator("#screen-google")).toBeVisible();
  });
});
