const { test } = require("@playwright/test");
const { TEST_USER, expect, preparePage } = require("./helpers/mock-codebug");

/**
 * Regression tests for the frontend security fixes:
 *  - H2: ?next= was assigned straight to location.href, giving an open redirect
 *        and javascript: execution right after a successful login.
 *  - L7: user-controlled values interpolated into innerHTML.
 */

test.describe("Безопасность: параметр next", () => {
  const ATTACKS = [
    "https://evil.example/",
    "//evil.example/",
    "javascript:window.__xss__=1",
    "JaVaScRiPt:window.__xss__=1",
    "data:text/html,<script>window.__xss__=1</script>",
    "\\\\evil.example",
  ];

  for (const attack of ATTACKS) {
    test(`не уводит на ${attack}`, async ({ page }) => {
      await preparePage(page);
      await page.goto("/auth.html");

      const resolved = await page.evaluate(
        (value) => window.safeNextTarget(value),
        attack
      );
      expect(resolved).toBe("index.html");
    });
  }

  test("сохраняет обычный относительный путь", async ({ page }) => {
    await preparePage(page);
    await page.goto("/auth.html");

    for (const [input, expected] of [
      ["profile.html", "profile.html"],
      ["train.html?id=3", "train.html?id=3"],
      ["/donate.html", "/donate.html"],
      ["", "index.html"],
    ]) {
      const resolved = await page.evaluate((v) => window.safeNextTarget(v), input);
      expect(resolved).toBe(expected);
    }
  });

  test("после входа с вредоносным next остаётся на сайте", async ({ page }) => {
    await preparePage(page);
    const xssFired = [];
    page.on("dialog", (d) => { xssFired.push(d.message()); d.dismiss(); });

    await page.goto("/auth.html?next=" + encodeURIComponent("https://evil.example/"));
    await page.locator("#login-identity").fill(TEST_USER.login);
    await page.locator("#login-pass").fill(TEST_USER.password);
    await page.getByRole("button", { name: "Войти" }).click();

    await expect(page).toHaveURL(/index\.html$/);
    expect(page.url()).not.toContain("evil.example");
    expect(xssFired).toEqual([]);
  });
});

test.describe("Безопасность: XSS в пользовательских полях", () => {
  test("вердикт с HTML не выполняется как разметка", async ({ page }) => {
    await preparePage(page, { authenticated: true });

    const payload = '<img src=x onerror="window.__xss__=1">';
    await page.goto("/submissions.html");

    // escapeHtml is the helper the submission table now runs the verdict through.
    const escaped = await page.evaluate((v) => {
      const fn = window.escapeHtml || ((s) => s);
      return fn(v);
    }, payload);

    expect(escaped).not.toContain("<img");
    expect(escaped).toContain("&lt;img");

    const fired = await page.evaluate(() => window.__xss__ === 1);
    expect(fired).toBe(false);
  });
});
