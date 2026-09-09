const { test } = require("@playwright/test");
const { expect, preparePage } = require("./helpers/mock-codebug");

test.describe("Профиль, соревнования и доступ", () => {
  test("тренировка показывает опыт и решённые задачи через защищённый API", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.goto("/train.html");
    await expect(page.locator("#metricSolved")).toHaveText("3");
    await expect(page.locator("#metricExp")).toHaveText("42");
    await expect(page.locator('.task-row[data-href="problem.html?id=101"] .solve-mark')).toHaveClass(/solved/);
  });

  test("профиль показывает актуальную статистику", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.goto("/profile.html");
    await expect(page.locator("#username")).toHaveText("e2e_user");
    await expect(page.locator("#osuSolvedCount")).toHaveText("1");
  });

  test("участник регистрируется, открывает задачу и видит таблицу", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.goto("/contest.html?id=e2e-contest");
    await expect(page.locator("#contestTitle")).toHaveText("E2E Контест");
    await page.getByRole("button", { name: "Зарегистрироваться" }).click();
    await expect(page.getByRole("button", { name: "Вы зарегистрированы" })).toBeDisabled();
    await expect(page.locator("#tasksList")).toContainText("Сумма двух чисел");
    await page.getByRole("button", { name: "Открыть" }).click();
    await expect(page).toHaveURL(/problem\.html\?id=101&contest=e2e-contest/);
  });

  test("FREE не получает право создавать приватное соревнование", async ({ page }) => {
    await preparePage(page, { authenticated: true, plan: "free" });
    await page.goto("/contests.html");
    await page.locator("#openCreateModal").click();
    await expect(page.locator("#selectPrivateContest")).toBeDisabled();
    await expect(page.locator("#selectGlobalContest")).toBeDisabled();
  });

  test("PRO+ создаёт приватное соревнование", async ({ page }) => {
    await preparePage(page, { authenticated: true, plan: "pro_plus" });
    let requestBody;
    await page.route("**/contests/create", async (route) => {
      requestBody = route.request().postDataJSON();
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ ok: true, contestId: "created-e2e" }) });
    });
    await page.goto("/contests.html");
    await page.locator("#openCreateModal").click();
    await page.locator("#selectPrivateContest").click();
    await page.locator("#ccTitle").fill("E2E приватный контест");
    await page.locator("#ccTasks").fill("101");
    await page.locator("#ccAllowed").fill("e2e_user");
    await page.locator("#ccStart").evaluate((node) => { node.value = String(Date.now() + 60_000); });
    await page.locator("#ccEnd").evaluate((node) => { node.value = String(Date.now() + 3_600_000); });
    await page.locator("#createContestForm").evaluate((form) => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
    await expect.poll(() => requestBody).toMatchObject({ title: "E2E приватный контест", tasks: [101], allowedUsers: ["e2e_user"], visibility: "private" });
  });
});
