const { test } = require("@playwright/test");
const { expect, preparePage, signInThroughUi } = require("./helpers/mock-codebug");

test.describe("Задачи и посылки", () => {
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
});
