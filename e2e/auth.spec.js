const { test } = require("@playwright/test");
const { TEST_USER, expect, preparePage, signInThroughUi } = require("./helpers/mock-codebug");

test.describe("Авторизация", () => {
  test("регистрация показывает экран подтверждения email", async ({ page }, testInfo) => {
    await preparePage(page);
    await page.goto("/auth.html");
    await page.getByText("Нет аккаунта? Регистрация").click();
    await page.locator("#reg-user").fill("fresh_user");
    await page.locator("#reg-email").fill("fresh_user@codebug.test");
    await page.locator("#reg-pass").fill(TEST_USER.password);
    await expect(page.locator("#reg-submit-btn")).toBeEnabled();
    const submit = page.locator("#reg-submit-btn");
    if (testInfo.project.name === "mobile") {
      await submit.focus();
      await page.keyboard.press("Enter");
    } else {
      await submit.click();
    }
    await expect(page.locator("#screen-verify")).toBeVisible();
    await expect(page.locator("#verify-email-label")).toHaveText("fresh_user@codebug.test");
  });

  test("вход, выход и восстановление пароля", async ({ page }) => {
    await preparePage(page);
    await page.goto("/auth.html");
    await page.locator("#login-identity").fill(TEST_USER.email);
    await page.getByText("Забыли пароль?").click();
    await expect(page.locator("#login-error")).toHaveText("Письмо для восстановления пароля отправлено");

    await signInThroughUi(page);
    await expect(page.locator("#nav-links")).toContainText(TEST_USER.login);
    await page.evaluate(() => window.logout());
    await expect(page).toHaveURL(/auth\.html$/);
    await expect(page.locator("#screen-login")).toBeVisible();
  });

  test("вход по логину не раскрывает email клиенту", async ({ page }) => {
    await preparePage(page);
    await page.goto("/auth.html");
    await page.locator("#login-identity").fill(TEST_USER.login);
    await page.locator("#login-pass").fill(TEST_USER.password);
    const loginRequest = page.waitForRequest("**/auth/login");
    await page.getByRole("button", { name: "Войти" }).click();
    const request = await loginRequest;
    expect(request.postDataJSON()).toEqual({ identity: TEST_USER.login, password: TEST_USER.password });
    await expect(page.locator("#nav-links")).toContainText(TEST_USER.login);
  });

  test("основная навигация ведёт на ожидаемые страницы", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.goto("/index.html");
    await expect(page.locator('#nav-links a[href="train.html"]').first()).toHaveText("Тренировка");
    await expect(page.locator('#nav-links a[href="contests.html"]').first()).toHaveText("Соревнования");
    await expect(page.locator('#nav-links a[href="rating.html"]').first()).toHaveText("Рейтинг");
    await expect(page.locator('#nav-links a[href="submissions.html"]').first()).toHaveText("Посылки");
  });
});
