const { test } = require("@playwright/test");
const { expect, preparePage, signInThroughUi } = require("./helpers/mock-codebug");

test.describe("Задачи и посылки", () => {
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
    await expect(page.locator("#editorFeedback")).toContainText("Буфер обмена отключён");

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
