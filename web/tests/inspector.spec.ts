import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("real episode: cameras, seek, signals, keyboard and desktop accessibility", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1512, height: 1100 });
  await page.goto("/?view=catalog&episode=0");
  await expect(
    page.getByRole("heading", {
      name: "pink lego brick into the transparent box",
    }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluateAll((v) =>
          v.every((x) => (x as HTMLVideoElement).readyState >= 2),
        ),
    )
    .toBeTruthy();
  await page.getByRole("button", { name: "Next sample", exact: true }).click();
  await expect(page.getByRole("slider", { name: "Episode time" })).toHaveValue(
    /0.033/,
  );
  await page.getByRole("button", { name: "Play", exact: true }).click();
  await expect
    .poll(() => page.getByRole("slider", { name: "Episode time" }).inputValue())
    .not.toBe("0.03333333333333333");
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page.getByRole("slider", { name: "Episode time" }).focus();
  await page.keyboard.press("ArrowRight");
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
  await page.screenshot({
    path: `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/inspector-desktop.png`,
    fullPage: true,
  });
});
test("narrow inspector fits and exposes numeric signals", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?view=catalog&episode=0");
  await expect(
    page.getByRole("heading", { name: "Robot signals" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByText(/Numeric sample at/).click();
  await expect(
    page.getByRole("columnheader", { name: "State", exact: true }),
  ).toBeVisible();
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
  await page.screenshot({
    path: `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/inspector-narrow.png`,
    fullPage: true,
  });
});
