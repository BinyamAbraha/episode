import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("recorded replay discloses provenance, plays real clips and shows verification", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(process.env.EPISODE_REPLAY_URL || "http://127.0.0.1:8767");
  await expect(
    page.getByText("Read-only recorded data. No live processing."),
  ).toBeVisible();
  await expect(page.locator("#source")).toContainText("Generated");
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
  await expect(page.locator("#cursor")).toContainText("0.03");
  await page
    .getByRole("button", { name: "Play recording", exact: true })
    .click();
  await expect
    .poll(() => page.locator("#seek").inputValue())
    .not.toBe("0.03333333333333333");
  await page
    .getByRole("button", { name: "Pause recording", exact: true })
    .click();
  await page.screenshot({
    path: `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/replay-desktop.png`,
    fullPage: true,
  });
  for (const name of [
    "2. Explain a finding",
    "3. Recorded curation",
    "4. Consumer evidence",
  ]) {
    await page.getByRole("button", { name, exact: true }).click();
    const a = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(a.violations).toEqual([]);
  }
  await expect(page.locator("#verification")).toContainText("passed:");
  await page
    .getByRole("button", { name: "5. Recorded model suggestions", exact: true })
    .click();
  await expect(page.locator("#analysis-source")).toContainText(
    "Model mlx-community",
  );
  await expect(
    page.locator("#analysis-suggestions article").first(),
  ).toContainText("Review required");
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "1. Inspect recording", exact: true })
    .click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  const a = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(a.violations).toEqual([]);
  await page.screenshot({
    path: `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/replay-narrow.png`,
    fullPage: true,
  });
});
