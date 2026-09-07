const { test } = require("@playwright/test");
const { TEST_USER, expect, preparePage } = require("./helpers/mock-codebug");

/**
 * The Content-Security-Policy is declared in a <meta> tag because GitHub Pages
 * cannot send headers. A CSP that blocks a resource the page needs breaks the page
 * silently, so this asserts the real browser reports no violations while the page
 * loads AND while the login flow runs.
 */
const CSP_PAGES = [
  "/auth.html", "/index.html", "/profile.html", "/rating.html", "/friends.html",
  "/submissions.html", "/contests.html", "/contest.html", "/donate.html",
  "/faq.html", "/train.html", "/404.html",
];

for (const path of CSP_PAGES) {
  test(`${path}: политика CSP не блокирует нужные ресурсы`, async ({ page }) => {
    const violations = [];
    page.on("console", (msg) => {
      const text = msg.text();
      // e2e-db.test is the mock harness's stand-in for the Realtime Database host.
      // Production uses *.firebaseio.com / *.firebasedatabase.app, which the policy
      // allows; adding a test-only host to the real policy would be wrong.
      if (text.includes("e2e-db.test")) return;
      if (/Content Security Policy|Refused to (load|connect|execute|apply)/i.test(text)) {
        violations.push(text);
      }
    });
    page.on("pageerror", (err) => violations.push(`pageerror: ${err.message}`));

    await preparePage(page);
    await page.goto(path);
    await page.waitForTimeout(1200);

    // The page must actually render, not just fail quietly behind a blocked script.
    await expect(page.locator("body")).toBeVisible();
    const csp = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute("content");
    expect(csp).toContain("https://*.europe-west1.firebasedatabase.app");
    expect(csp).toContain("wss://*.firebasedatabase.app");
    expect(csp).toContain("wss://*.firebaseio.com");
    expect(csp).toMatch(/frame-src[^;]*https:\/\/\*\.europe-west1\.firebasedatabase\.app/);
    expect(violations, `CSP violations on ${path}:\n${violations.join("\n")}`).toEqual([]);
  });
}

test("auth.html: вход работает при включённом CSP", async ({ page }) => {
  const violations = [];
  page.on("console", (msg) => {
    const text = msg.text();
    if (/Content Security Policy|Refused to (load|connect|execute|apply)/i.test(text)) {
      violations.push(text);
    }
  });

  await preparePage(page);
  await page.goto("/auth.html");
  await page.locator("#login-identity").fill(TEST_USER.login);
  await page.locator("#login-pass").fill(TEST_USER.password);
  await page.getByRole("button", { name: "Войти" }).click();

  await expect(page).toHaveURL(/index\.html$/);
  expect(violations, `CSP violations during login:\n${violations.join("\n")}`).toEqual([]);
});

test("auth.html: CSP запрещает опасные директивы", async ({ page }) => {
  await preparePage(page);
  await page.goto("/auth.html");
  const csp = await page.evaluate(() => {
    const el = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
    return el ? el.getAttribute("content").replace(/\s+/g, " ").trim() : null;
  });
  expect(csp).toBeTruthy();
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("base-uri 'self'");
  // frame-ancestors is intentionally NOT here: it is ignored in a meta tag.
  expect(csp).not.toContain("frame-ancestors");
  expect(csp).toContain("form-action 'self'");
  // script-src must be host-pinned, never a blanket https: or *.
  expect(csp).toMatch(/script-src[^;]*gstatic\.com/);
  expect(csp).not.toMatch(/script-src[^;]*\*\s/);
});
