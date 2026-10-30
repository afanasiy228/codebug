const { test } = require("@playwright/test");
const { expect, preparePage, signInThroughUi } = require("./helpers/mock-codebug");

test.describe("Задачи и посылки", () => {
  for (const [labelTag, duplicate] of [["h2", true], ["h2", false], ["p", true], ["p", false]]) {
    test(`${labelTag}: ${duplicate ? "совпадающий пример показывается один раз и кнопки центрированы" : "отличающийся пример в условии сохраняется"}`, async ({ page }) => {
      await preparePage(page, { authenticated: true });
      await page.route("**/tasks/101/view", route => route.fulfill({ json: {
        meta: { title: "Примеры", language: "cpp", statement: { html: "statement/russian.html" }, files: { code: "code.cpp" }, openTests: [{ name: "001", input: "tests/1.in", answer: "tests/1.out" }] },
        files: {
          "statement/russian.html": `<h1>Примеры</h1><h2>Формат входных данных</h2><p>Даны числа.</p><${labelTag}>Пример входных данных</${labelTag}><pre><code>5 3\n1 2 -1 3 0\n</code></pre><${labelTag}>Пример выходных данных</${labelTag}><pre><code>${duplicate ? "3" : "9"}\n</code></pre><h2>Пояснение</h2><p>Это пояснение нужно сохранить.</p>`,
          "code.cpp": "int main() {}", "tests/1.in": "5 3\n1 2 -1 3 0\n", "tests/1.out": "3\n"
        }
      } }));
      await page.goto("/problem.html?id=101");
      await expect(page.locator("#examples .testcase-block")).toHaveCount(1);
      await expect(page.locator("#taskStatement pre")).toHaveCount(duplicate ? 0 : 2);
      await expect(page.locator("#taskStatement")).toContainText("Формат входных данных");
      await expect(page.locator("#taskStatement")).toContainText("Это пояснение нужно сохранить.");
      await page.evaluate(() => setStatementLanguage("ru"));
      await expect(page.locator("#taskStatement pre")).toHaveCount(duplicate ? 0 : 2);
      const geometry = await page.locator("#examples .kf-io").evaluateAll(blocks => blocks.map(block => {
        const outer = block.getBoundingClientRect(), button = block.querySelector("button").getBoundingClientRect(), code = block.querySelector("pre").getBoundingClientRect();
        return { centerError: Math.abs((outer.top + outer.bottom - button.top - button.bottom) / 2), overlaps: code.right > button.left };
      }));
      expect(geometry.every(item => item.centerError < 1 && !item.overlaps)).toBe(true);
    });
  }

  test("пакет задачи показывает условие и примеры без отдельных запросов файлов", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    const fileRequests = [];
    await page.route("**/tasks/101/**", async route => {
      if (route.request().url().endsWith("/view")) {
        return route.fulfill({ json: {
          meta: { title: "Быстрый пакет", language: "cpp", statement: { markdown: "statement.md" }, files: { code: "code.cpp" }, openTests: [{ input: "tests/1.in", answer: "tests/1.out" }] },
          files: { "statement.md": "# Условие\nДанные из одного пакета.", "code.cpp": "int main() {}", "tests/1.in": "2 3", "tests/1.out": "5" }
        } });
      }
      fileRequests.push(route.request().url());
      return route.abort();
    });
    await page.goto("/problem.html?id=101");
    await expect(page.locator("#taskTitle")).toHaveText("Быстрый пакет");
    await expect(page.locator("#taskStatement")).toContainText("Данные из одного пакета.");
    await expect(page.locator("#examples")).toContainText("2 3");
    await expect.poll(() => page.evaluate(() => window.editor?.getValue())).toBe("int main() {}");
    expect(fileRequests).toEqual([]);
  });

  test("лимит правок блокирует отправку переписанного решения", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.route("**/tasks/101/problem.json", async (route) => {
      await route.fulfill({ json: {
        title: "Лимит правок", language: "cpp", difficulty: "easy", maxChangedLines: 1,
        statement: { markdown: "statement.md" }, files: { code: "code.cpp" }
      } });
    });
    await page.goto("/problem.html?id=101");
    await expect(page.locator("#changeCounter")).toHaveText("Изменено строк: 0 из 1");
    let submitted = false;
    page.on("request", request => { if (request.url().endsWith("/submit")) submitted = true; });
    await page.evaluate(() => window.editor.setValue("int x;\nint y;\nint z;\nint main() {}"));
    const dialogPromise = page.waitForEvent("dialog");
    await page.evaluate(() => { setTimeout(() => submitCode(), 0); });
    const dialog = await dialogPromise;
    expect(dialog.message()).toContain("для исправления хватает 1");
    await dialog.accept();
    expect(submitted).toBe(false);
  });

  test("редактор блокирует операции с буфером обмена", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.goto("/problem.html?id=101");

    const blocked = await page.locator("#editor").evaluate((root) => {
      const result = {};
      for (const type of ["copy", "cut", "paste", "contextmenu", "dragstart", "drop"]) {
        const event = new Event(type, { bubbles: true, cancelable: true });
        root.dispatchEvent(event);
        result[type] = event.defaultPrevented;
      }
      const shortcut = new KeyboardEvent("keydown", {
        key: "v",
        ctrlKey: true,
        bubbles: true,
        cancelable: true
      });
      root.dispatchEvent(shortcut);
      result.shortcut = shortcut.defaultPrevented;
      const legacyCut = new KeyboardEvent("keydown", {
        key: "Delete",
        shiftKey: true,
        bubbles: true,
        cancelable: true
      });
      root.dispatchEvent(legacyCut);
      result.legacyCut = legacyCut.defaultPrevented;
      const beforePaste = new InputEvent("beforeinput", {
        inputType: "insertFromPaste",
        bubbles: true,
        cancelable: true
      });
      root.dispatchEvent(beforePaste);
      result.beforePaste = beforePaste.defaultPrevented;
      return result;
    });

    expect(blocked).toEqual({
      copy: true,
      cut: true,
      paste: true,
      contextmenu: true,
      dragstart: true,
      drop: true,
      shortcut: true,
      legacyCut: true,
      beforePaste: true
    });
    await expect(page.locator("#editorFeedback")).toContainText("Вставить можно только то, что скопировано в редакторе");

    const regularFieldPaste = await page.locator("#customInput").evaluate((field) => {
      const event = new Event("paste", { bubbles: true, cancelable: true });
      field.dispatchEvent(event);
      return event.defaultPrevented;
    });
    expect(regularFieldPaste).toBe(false);
  });

  test("пользователь открывает задачу и получает вердикт", async ({ page }, testInfo) => {
    await preparePage(page);
    await signInThroughUi(page);
    await page.goto("/problem.html?id=101");
    await expect(page.locator("#taskTitle")).toHaveText("Сумма двух чисел");
    await expect(page.locator("#taskStatement")).toContainText("Даны два числа");

    await page.evaluate(() => window.editor.setValue("#include <iostream>\nint main(){return 0;}"));
    const submit = page.getByRole("button", { name: "Отправить" });
    if (testInfo.project.name === "mobile") {
      await submit.focus();
      await page.keyboard.press("Enter");
    } else {
      await submit.click();
    }
    await expect(page.locator("#subs")).toContainText("OK");
  });

  test("по нажатию на CE открывается ошибка компилятора", async ({ page }) => {
    await preparePage(page, { authenticated: true });
    await page.route("**/submissions/e2e-ce/diagnostics", (route) => route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        submissionId: "e2e-ce",
        verdict: "CE",
        details: "sol.cpp:4:9: error: expected ';' before 'return'"
      })
    }));
    await page.goto("/problem.html?id=101");
    await page.evaluate(async () => {
      window.__e2eStore.submissions.global["e2e-ce"] = {
        login: "e2e_user",
        task: 101,
        verdict: "CE",
        statusLabel: "CE",
        date: Date.now()
      };
      await window.loadMySubsForThisProblem();
    });

    const verdict = page.getByRole("button", { name: "CE" });
    await expect(verdict).toHaveAttribute("title", "Показать ошибку компиляции");
    await expect(verdict).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(verdict).toHaveCSS("color", "rgb(228, 123, 85)");
    await expect(verdict).toHaveCSS("text-decoration-line", "underline");
    await expect(page.getByRole("button", { name: "RU" })).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(page.getByRole("button", { name: "EN" })).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await verdict.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("dialog", { name: "Подробности ошибки компиляции" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ошибка компиляции" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Закрыть" })).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
    await expect(page.getByRole("button", { name: "Закрыть" })).toHaveCSS("border-top-width", "0px");
    await expect(page.getByRole("button", { name: "Закрыть" })).toHaveCSS("outline-style", "none");
    await expect(page.locator(".compilation-diagnostics-output")).toContainText("expected ';' before 'return'");
  });

  test("пользователь запускает код на своих данных", async ({ page }, testInfo) => {
    await preparePage(page, { authenticated: true });
    await page.goto("/problem.html?id=101");

    await expect(page.locator("#taskTitle")).toHaveText("Сумма двух чисел");
    await expect(page.locator("#examples")).toContainText("Тест 1");
    await expect(page.locator("#customInput")).toBeHidden();
    const runSummary = page.getByText("Запуск на своих данных");
    if (testInfo.project.name === "mobile") {
      await runSummary.focus();
      await page.keyboard.press("Enter");
    } else {
      await runSummary.click();
    }
    await page.locator("#customInput").fill("2 3");
    const runButton = page.getByRole("button", { name: "Запустить", exact: true });
    if (testInfo.project.name === "mobile") {
      await runButton.focus();
      await page.keyboard.press("Enter");
    } else {
      await runButton.click();
    }

    await expect(page.locator("#customOutput")).toHaveText("5");
    await expect(page.locator("#customRunStatus")).toContainText("Готово");
  });

  test("просроченный токен не отправляется повторно", async ({ page }) => {
    await preparePage(page);
    let requests = 0;
    await page.route("**/submit", async (route) => {
      requests += 1;
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ code: "INVALID_TOKEN" })
      });
    });
    await page.goto("/problem.html?id=101");
    await page.evaluate(() => {
      window.getFreshAuthToken = ({ forceRefresh } = {}) => Promise.resolve(forceRefresh ? null : "stale-token");
    });

    const error = await page.evaluate(async () => {
      try {
        await window.sendToJudge(101, "int main(){}", "legacy");
        return null;
      } catch (cause) {
        return { code: cause.code, message: cause.message };
      }
    });

    expect(error).toEqual({ code: "AUTH_SESSION_EXPIRED", message: "Сессия истекла. Войди в аккаунт снова" });
    expect(requests).toBe(1);
  });
});
